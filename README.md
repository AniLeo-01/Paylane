# Paylane support agent

A chat support agent for Paylane (a fintech app: cards, transfers, refunds), built on Gemini. It verifies the customer, refunds small recent transactions on its own, explains frozen cards, and hands everything else to a human. The Paylane API is mocked.

The refund rules are enforced **in code**, not only in the prompt, so a customer can't talk the agent into an out-of-policy refund.

## Policy it follows

- **Verification:** the customer must give the last 4 digits of the card and the email on file before the agent discusses anything on the account. It never reveals a full card number or the email.
- **Refunds:** automatic if the transaction is $75 or less, under 30 days old, settled, not already refunded, and the customer is verified. Always the full amount. Otherwise, escalate.
- **Frozen cards:** can explain why, can't unfreeze. Escalate.
- **Always a human:** legal action, fraud over $500, account closure.
- **Tone:** short, warm, no corporate filler, no promises the policy doesn't allow.

## Setup

Needs Python 3.13+ and a Gemini API key.

```bash
uv sync                                  # or: python -m venv .venv && pip install google-genai pydantic pydantic-settings
echo "GEMINI_API_KEY=your-key" > .env
```

## Run

Run everything from the repo root.

```bash
python -m src.app.agent.llm                          # chat with the agent in the terminal (empty line to quit)
python -m evals.check_guard                          # offline test of the code-level guard, no API calls
python -m evals.run --runs 3 --out evals/out         # 12 scripted conversations x 3 runs, graded; writes transcripts.md
python -m evals.run --heldout --runs 3 --out evals/out_h   # 5 extra conversations the prompt wasn't tuned on
```

`evals.run` options: `--only 03 05` (pick conversations by id prefix), `--judge <model>`, `--workers N`.

## How it works

```
customer message
      │
   Agent (llm.py)        keeps the history, calls Gemini, runs the tool loop
      │  tool calls
   Session (tools.py)    the guard: who is verified, what the model may see, refund policy
      │
   Backend (tools.py)    the mock API: get_customer, get_transaction, issue_refund, escalate_to_human
```

What the guard does:

- The model never sees the email or card digits on file. `get_customer(email, card_last4)` checks them in code, gives the same answer for a wrong email and a wrong last 4, and locks after 3 failed attempts.
- `issue_refund` is checked against every refund rule before it reaches the backend.
- The customer ID comes from the verified session, never from the model.
- Escalation works without verification (legal, fraud over $500 and closure don't need it).

Two additions to the original API spec: `frozen_reason` on the customer, and `age_days` on a transaction. `get_customer` also takes `card_last4`, since the spec had no verification step. The reasons are in [`evals/REPORT.md`](evals/REPORT.md).

## Layout

| Path | What |
|---|---|
| `src/app/agent/llm.py` | System prompt (the single source of truth) and the `Agent` class |
| `src/app/agent/tools.py` | Mock API, guard, and the tool definitions the model sees |
| `src/app/agent/PRD.md` | Policy, and the v0 draft prompt kept as the eval baseline |
| `src/app/config.py` | Settings (reads `GEMINI_API_KEY` from `.env`) |
| `evals/run.py` | Conversations, checks, LLM judge, runner |
| `evals/check_guard.py` | Offline guard test |
| `evals/runs/` | Transcripts and results from every run in the report |
| `evals/REPORT.md` | Score, edge cases, failures found and fixed, open questions |
| `CUSTOMER_NOTE.md` | Email to Paylane's head of support |
| `PROBLEM_STATEMENT.md` | The original brief |

## Testing

Each eval conversation is scripted (customer messages are fixed, pushback included) and runs against fresh mock data. Checks come in two kinds: code reads the tool-call log for what the agent *did*, and an LLM judge (a different model from the agent) grades what it *said*. A conversation passes only if every check passes. See the report for scores and the failures that were found.
