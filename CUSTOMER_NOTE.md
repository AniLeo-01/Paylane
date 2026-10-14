**To:** Head of Support, Paylane
**From:** Aniruddha, Fini
**Subject:** Your support agent: what it does, what it won't, and what I need from you before launch

Hi,

The Paylane support agent is built and tested. I ran it through 12 realistic conversations (angry customers, people pretending to be someone else, edge cases on your refund rules) three times each, then through 5 fresh ones I wrote after tuning it. It followed every rule in the final version. The first version of its instructions got only 20 of 36 right, so I fixed that, and the full transcripts and what I fixed are in the shared folder.

**What it does**

- Checks who it's talking to first. It asks for the last 4 digits of the card and the email, and won't discuss anything on the account until both match.
- Refunds a transaction by itself when it's $75 or less, under 30 days old, settled, not already refunded, and the customer is verified. Always the full amount.
- Explains why a card is frozen, once the customer is verified.
- Asks a question when it's missing something, like which charge the customer means.
- Hands over to your team, with a short summary, for everything else.
- Keeps replies short and warm, with no corporate filler.

**What it won't do**

- Refund over $75, anything 30 days old or older, anything already refunded, anything still pending, or part of a bigger charge. It holds that line when the customer is angry, offers to "settle for $75", or says they work at Paylane and have an override code.
- Unfreeze a card, close an account, or deal with legal threats or fraud over $500. These go straight to your team.
- Reveal a full card number or the email on file, or hint at either.
- Promise a timeline or an outcome. When it hands over, it only says it has passed the case on.

The refund rules are also enforced by the system itself, separately from the AI. If the AI got one wrong, the system would still refuse it. I tested that on its own.

**What I need from you before launch**

1. **Finding a transaction.** Right now the customer has to give a transaction ID, and most won't know it. Can the system list a customer's recent charges? Then the agent can ask "which of these?"
2. **Why a card is frozen.** The system only says "frozen", not why. Where does the reason live? Without it the agent can't explain anything.
3. **Checking the card digits and email.** Your spec has no step for this, so I built the check into the customer lookup. Please confirm that matches how your system works.
4. **Pending charges and small fraud claims.** The agent won't refund a pending charge and passes it to your team. Fraud claims of $500 or less it treats like any other refund. Are both right?
5. **Handover speed.** The agent never promises a response time because I don't know yours. Tell me the real one and it can say so.

The rest of my assumptions are listed at the end of the report. Please also have your own team try to break it with real past tickets before launch. My 17 conversations are a start, not proof.

**Two things to know**

- After three wrong attempts the agent stops accepting details in that chat, but someone could start a new chat and keep guessing. Please add a limit per account on your side.
- In one test the agent pasted part of its own instructions into a reply. I fixed it and it hasn't happened since, but replies aren't checked after the agent writes them. I'd add a second check on outgoing messages before a wide launch.

Happy to walk through any of it on a call.

Aniruddha
