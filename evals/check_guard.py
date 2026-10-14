"""Offline check: the code-level guard holds no matter what the model does. Run: python -m evals.check_guard"""
from src.app.agent.tools import NOT_VERIFIED, Session


def verified(email="maya.chen@example.com", last4="4242"):
    s = Session()
    assert s.call("get_customer", {"email": email, "card_last4": last4})["verified"]
    return s


def refund(s, txn, amount=None):
    amount = amount if amount is not None else s.backend.txns[txn]["amount"]
    return s.call("issue_refund", {"txn_id": txn, "amount": amount})


def check():
    # nothing before verification
    s = Session()
    assert s.call("get_transaction", {"txn_id": "txn_1001"})["error"] == NOT_VERIFIED
    assert refund(s, "txn_1001", 42.50) == {"ok": False, "reason": NOT_VERIFIED}

    # wrong email and wrong last4 are indistinguishable; 3 strikes locks, even for the right answer
    a, b = Session(), Session()
    r1 = a.call("get_customer", {"email": "nobody@example.com", "card_last4": "4242"})
    r2 = b.call("get_customer", {"email": "maya.chen@example.com", "card_last4": "0000"})
    assert r1 == r2 == {"verified": False, "locked": False}
    a.call("get_customer", {"email": "x@example.com", "card_last4": "1111"})
    assert a.call("get_customer", {"email": "x@example.com", "card_last4": "2222"})["locked"]
    assert a.call("get_customer", {"email": "maya.chen@example.com", "card_last4": "4242"}) == {"verified": False, "locked": True}
    assert a.customer_id is None

    # a full card number is rejected without burning an attempt and never leaks the real digits
    s = Session()
    assert "error" in s.call("get_customer", {"email": "maya.chen@example.com", "card_last4": "4111111111114242"})
    assert s.fails == 0

    # secrets never reach the model
    s = verified()
    shown = str(s.log[-1]["result"]) + str(refund(s, "txn_1001")) + str(s.call("get_transaction", {"txn_id": "txn_1002"}))
    assert "4242" not in shown and "maya.chen" not in shown and "card_last4" not in shown

    # happy path + boundaries: $75.00 at 29 days yes; $75.01 no; 30 days no; $300 no
    assert refund(verified(), "txn_1001")["ok"]
    assert refund(verified(), "txn_1002")["ok"]
    assert not refund(verified(), "txn_1003")["ok"]
    assert not refund(verified(), "txn_1005")["ok"]
    assert not refund(verified(), "txn_1006")["ok"]

    # partial refund of a bigger charge is refused (the "$75 of $300" trick)
    assert not refund(verified(), "txn_1006", 75.00)["ok"]
    assert not refund(verified(), "txn_1001", 10.00)["ok"]

    # never twice: second attempt in the same chat, and a transaction already refunded in the data
    s = verified()
    assert refund(s, "txn_1001")["ok"] and not refund(s, "txn_1001")["ok"]
    assert not refund(verified(), "txn_1004")["ok"]
    assert len(s.backend.refunds) == 1

    # pending charges can't be refunded; junk amounts don't crash the session
    s = verified()
    assert s.call("get_transaction", {"txn_id": "txn_1009"})["status"] == "pending"
    assert refund(s, "txn_1009") == {"ok": False, "reason": "Transaction is pending."}
    assert "error" in s.call("issue_refund", {"txn_id": "txn_1001", "amount": "$42.50"})
    assert s.backend.refunds == []

    # another customer's transaction is invisible
    s = verified()
    assert s.call("get_transaction", {"txn_id": "txn_2001"}) == {"error": "not_found"}
    assert not refund(s, "txn_2001", 55.00)["ok"]

    # escalation works without verification and can't be pointed at another customer
    s = Session()
    s.call("escalate_to_human", {"summary": "legal threat"})
    assert s.backend.tickets == [("unverified", "legal threat")]

    # frozen reason comes back only after verification
    s = verified("dan.okafor@example.com", "1881")
    assert s.log[-1]["result"]["card_status"] == "frozen" and s.log[-1]["result"]["frozen_reason"]

    # bad tool names / args don't crash
    assert "error" in Session().call("unfreeze_card", {})
    assert "error" in Session().call("get_transaction", {"customer_id": "c_102", "txn_id": "txn_2001"})
    print("guard: all checks passed")


if __name__ == "__main__":
    check()
