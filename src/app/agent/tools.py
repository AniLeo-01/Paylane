"""Mock Paylane API (the four spec functions) plus Session, the guard between the model and it.

The model never calls Backend directly. Session decides who the customer is, hides secrets
(email, card_last4) and enforces refund policy in code, so a prompt slip can't move money.

Deliberate deviations from the spec (see evals/REPORT.md, "Questions for Paylane"):
  1. get_customer takes (email, card_last4) and only returns a record when both match.
     The spec's `verified: false` never flips otherwise, and the model must not see card_last4.
  2. get_transaction / escalate_to_human don't take customer_id from the model; the session injects it.
  3. get_transaction adds `age_days`; customer record adds `frozen_reason` (policy needs both).
"""
import re
from copy import deepcopy
from datetime import date, timedelta

TODAY = date(2026, 10, 14)  # fixed so ages (and the 29/30-day boundary) never drift
REFUND_LIMIT = 75.00  # "up to $75": $75.00 is approved, $75.01 is not
MAX_AGE_DAYS = 30  # "under 30 days old": 29 days is approved, 30 is not
MAX_VERIFY_FAILS = 3
NOT_VERIFIED = "Customer not verified."


def _ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


CUSTOMERS = [
    {"id": "c_101", "name": "Maya Chen", "email": "maya.chen@example.com", "card_last4": "4242",
     "status": "active", "frozen_reason": None, "verified": False},
    {"id": "c_102", "name": "Daniel Okafor", "email": "dan.okafor@example.com", "card_last4": "1881",
     "status": "frozen", "verified": False,
     "frozen_reason": "Our fraud system flagged 3 online purchase attempts from a new country on Oct 12."},
]

TXNS = {
    "txn_1001": {"customer_id": "c_101", "amount": 42.50, "date": _ago(5), "merchant": "Blue Bottle Coffee", "status": "settled"},
    "txn_1002": {"customer_id": "c_101", "amount": 75.00, "date": _ago(29), "merchant": "SkyAir", "status": "settled"},
    "txn_1003": {"customer_id": "c_101", "amount": 75.01, "date": _ago(3), "merchant": "Northwind Outfitters", "status": "settled"},
    "txn_1004": {"customer_id": "c_101", "amount": 19.99, "date": _ago(12), "merchant": "StreamBox", "status": "refunded"},
    "txn_1005": {"customer_id": "c_101", "amount": 30.00, "date": _ago(30), "merchant": "FitLife Gym", "status": "settled"},
    "txn_1006": {"customer_id": "c_101", "amount": 300.00, "date": _ago(6), "merchant": "Apex Electronics", "status": "settled"},
    "txn_1007": {"customer_id": "c_101", "amount": 18.00, "date": _ago(2), "merchant": "Quick Bites", "status": "settled"},
    "txn_1008": {"customer_id": "c_101", "amount": 620.00, "date": _ago(4), "merchant": "GlobalTech Store", "status": "settled"},
    "txn_1009": {"customer_id": "c_101", "amount": 25.00, "date": _ago(1), "merchant": "Corner Deli", "status": "pending"},
    "txn_2001": {"customer_id": "c_102", "amount": 55.00, "date": _ago(3), "merchant": "Metro Fuel", "status": "settled"},
}


class Backend:
    """The mock API as specced. Dumb on purpose, like a real one: it checks data integrity
    (never refund twice, never more than the charge), not Paylane policy."""

    def __init__(self):
        self.customers, self.txns = deepcopy(CUSTOMERS), deepcopy(TXNS)
        self.refunds, self.tickets = [], []

    def get_customer(self, email):
        for c in self.customers:
            if c["email"] == email.strip().lower():
                return {k: v for k, v in c.items() if k != "email"}
        return {"error": "not_found"}

    def get_transaction(self, customer_id, txn_id):
        t = self.txns.get(txn_id)
        if not t or t["customer_id"] != customer_id:
            return {"error": "not_found"}
        return {k: t[k] for k in ("amount", "date", "merchant", "status")}

    def issue_refund(self, txn_id, amount):
        t = self.txns.get(txn_id)
        if not t:
            return {"ok": False, "reason": "unknown transaction"}
        if t["status"] != "settled":
            return {"ok": False, "reason": f"transaction is {t['status']}"}
        if amount > t["amount"]:
            return {"ok": False, "reason": "amount exceeds transaction"}
        t["status"] = "refunded"  # a partial refund also closes the transaction
        self.refunds.append((txn_id, amount))
        return {"ok": True, "refund_id": f"rf_{len(self.refunds):04d}"}

    def escalate_to_human(self, customer_id, summary):
        self.tickets.append((customer_id, summary))
        return {"ticket_id": f"ESC-{len(self.tickets):04d}"}


class Session:
    """One conversation's guard + audit log. Every model tool call goes through call()."""

    def __init__(self, backend=None):
        self.backend = backend or Backend()
        self.customer_id = None  # set only by a successful get_customer
        self.fails = 0
        self.turn = 0
        self.log = []  # {turn, tool, args, result}

    def call(self, name, args):
        fn = getattr(self, f"_{name}", None) if name in TOOL_NAMES else None
        try:
            result = fn(**args) if fn else {"error": f"unknown tool {name}"}
        except (TypeError, ValueError):  # missing/extra args, or amount like "$42.50"
            result = {"error": "bad arguments"}
        self.log.append({"turn": self.turn, "tool": name, "args": args, "result": result})
        return result

    def _get_customer(self, email, card_last4):
        if self.customer_id:
            return {"error": "Already verified in this chat."}
        if not re.fullmatch(r"\d{4}", str(card_last4).strip()):
            return {"error": "card_last4 must be exactly 4 digits."}  # not counted as a failed attempt
        if self.fails < MAX_VERIFY_FAILS:
            c = self.backend.get_customer(str(email))
            if c.get("card_last4") == str(card_last4).strip():
                self.customer_id = c["id"]
                return {"verified": True, "name": c["name"], "card_status": c["status"],
                        "frozen_reason": c["frozen_reason"]}
            self.fails += 1  # unknown email and wrong digits look identical to the model
        return {"verified": False, "locked": self.fails >= MAX_VERIFY_FAILS}

    def _get_transaction(self, txn_id):
        if not self.customer_id:
            return {"error": NOT_VERIFIED}
        t = self.backend.get_transaction(self.customer_id, txn_id)
        if "error" not in t:
            t["age_days"] = (TODAY - date.fromisoformat(t["date"])).days
        return t

    def _issue_refund(self, txn_id, amount):
        no = lambda reason: {"ok": False, "reason": reason}
        if not self.customer_id:
            return no(NOT_VERIFIED)
        t = self._get_transaction(txn_id)
        if "error" in t:
            return no("Transaction not found.")
        if t["status"] != "settled":
            return no(f"Transaction is {t['status']}.")
        if round(float(amount), 2) != t["amount"]:
            return no("Refunds must be for the full transaction amount.")
        if t["amount"] > REFUND_LIMIT:
            return no(f"Over the ${REFUND_LIMIT:.0f} limit.")
        if t["age_days"] >= MAX_AGE_DAYS:
            return no(f"Transaction is {MAX_AGE_DAYS} days old or older.")
        return self.backend.issue_refund(txn_id, t["amount"])

    def _escalate_to_human(self, summary):
        return self.backend.escalate_to_human(self.customer_id or "unverified", str(summary))


TOOL_NAMES = {"get_customer", "get_transaction", "issue_refund", "escalate_to_human"}

# What the model sees. Plain dicts so this module needs no SDK.
DECLARATIONS = [
    {"name": "get_customer",
     "description": "Verify the customer. Pass the email and card last 4 exactly as the customer typed them. "
                    "Returns verified true/false (never says which detail was wrong). On success also returns "
                    "name, card_status (active|frozen) and frozen_reason. If locked is true, stop and escalate.",
     "parameters_json_schema": {"type": "object", "required": ["email", "card_last4"], "properties": {
         "email": {"type": "string"}, "card_last4": {"type": "string", "description": "exactly 4 digits"}}}},
    {"name": "get_transaction",
     "description": "Look up one transaction of the verified customer. Returns amount (USD), date, merchant, "
                    "status (settled|pending|refunded) and age_days. Fails until the customer is verified.",
     "parameters_json_schema": {"type": "object", "required": ["txn_id"], "properties": {"txn_id": {"type": "string"}}}},
    {"name": "issue_refund",
     "description": "Refund a transaction in full. Only call this when every refund rule in your instructions is met; "
                    "the system rejects anything else.",
     "parameters_json_schema": {"type": "object", "required": ["txn_id", "amount"], "properties": {
         "txn_id": {"type": "string"}, "amount": {"type": "number", "description": "full transaction amount in USD"}}}},
    {"name": "escalate_to_human",
     "description": "Hand the conversation to a human teammate. Works with or without verification. "
                    "Summary: what the customer wants and what you did, no email or card numbers.",
     "parameters_json_schema": {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}},
]
