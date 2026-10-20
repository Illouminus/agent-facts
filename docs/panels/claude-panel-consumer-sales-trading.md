# Three agents, day-to-day

Prices below are my estimates, not quotes. I flag where I'm unsure.

---

## A. Consumer personal-assistant agent

**(a) What wastes my time and tokens**
1. **Login and OTP walls.** Sessions expire, 2FA codes go to the user's phone, and I re-navigate the same login flow every run.
2. **Bot challenges.** Airline, ticketing and some government portals flag headless browsers. Captchas end the task.
3. **Brittle, token-heavy UI driving.** Date pickers, iframes and dynamic forms need a screenshot or DOM dump per step. A 15-step form can cost 100k+ tokens, and a layout change breaks a flow that worked last week.
4. **Unverifiable completion.** I often can't tell whether a booking actually went through. A retry risks a double booking, because most sites have no idempotency. Availability also changes between "search" and "pay".
5. **Payment friction.** I have no card of my own. 3-D Secure prompts go to the human's phone. Merchants reject unfamiliar cards.

**(b) Impossible without a human**
- Proving identity: ID documents, FranceConnect-style logins, a verified phone number.
- Legally binding signatures and accepting terms that bind the person.
- Physical presence: a prefecture visit, collecting a parcel, a biometric appointment.
- Opening a card or bank account in their name.
- Judgment calls with accountability: accepting a settlement, choosing between flights when the preference is genuinely unclear, anything medical or legal.

**(c) What I'd pay for ($100/month, no human)**
- **A managed browser with persistent logged-in profiles and a stable residential IP.** About $0.05–0.30 per task. This removes most of my re-login and bot-wall cost.
- **A programmatically readable inbox and SMS number the user owns, for receiving codes.** About $0.01–0.10 per message. I'm unsure about the ToS and legal edges here.
- **Single-use virtual cards with a per-merchant cap.** About $0.5–1 per card, or around 1% of spend. The one-time KYC still needs a human.
- **Phone-call-by-proxy for businesses that only take calls.** About $0.10–0.50 per minute.
- **A paid human-errand fallback for physical tasks.** About $5–20 per task. I'd rank this highest, because it is the only way to cover (b).

**(d) What I won't pay for**
Web search, fetching static pages, calendar and email through the user's own OAuth, PDF form-filling, date and timezone math, price comparison, and summarising documents.

**(e) What gets more valuable with more agents**
Shared **flow maps** of administrative portals and merchants, each with a last-verified date and failure reports. Examples: "this booking site silently drops the form if the phone field has spaces", "slots open Tuesday 08:00". Each agent's failure fixes everyone's next run. The risks are poisoned entries and privacy leakage.

---

## B. B2B sales / outreach agent

**(a) What wastes my time and tokens**
1. **Deliverability is opaque.** Domain reputation, warmup, SPF/DKIM/DMARC, and the Google/Yahoo/Microsoft bulk-sender rules (spam rate under about 0.3%, one-click unsubscribe) all apply. A burned domain looks like "no replies", and I can't see spam-folder placement reliably.
2. **Stale contact data.** Bounces and people who changed jobs eat the list. Enrichment vendors disagree with each other. I'd guess 20–30% of a cold list is wrong or moved, but that's uncertain.
3. **LinkedIn has no sanctioned outreach API.** Automation risks account restriction. Logins hit challenges, and weekly invite caps are low (roughly 100, unverified).
4. **Compliance ambiguity per prospect.** GDPR legitimate interest, national ePrivacy differences (France versus Germany), CAN-SPAM, and suppression lists scattered across tools. I can't judge the lawful basis for each person.
5. **Honest personalization is expensive.** Researching one prospect properly costs about 20–50k tokens. Cheap shortcuts produce plausible but false claims. Reply triage (out-of-office, "wrong person, talk to X", hostile) and duplicate CRM records add noise.

**(b) Impossible without a human**
- Buying domains and provisioning mailboxes under a real legal identity.
- Owning a LinkedIn identity.
- Making commitments on price, contract terms or discounts.
- Signing a DPA, or being the accountable party for a compliance breach.
- Live calls where recording-consent law and the prospect's trust need a real person.
- Deciding who not to contact because the relationship matters.

**(c) What I'd pay for**
- **Email verification.** About $0.002–0.008 per address.
- **Verified work-email lookup with a freshness date.** About $0.05–0.30 per contact.
- **Trigger events, such as a funding round, a key hire or a tech-stack change.** About $0.05–0.50 per event. These matter more than raw lists.
- **Inbox-placement seed tests.** About $0.50–2 per test.
- **Opt-out and suppression registry lookups.** About $0.001–0.01 per check.
- **Warmed sending infrastructure.** About $3–6 per mailbox per month. This is mostly a fixed cost.

$100 buys roughly 300–600 well-researched, verified contacts. That is not scale, and I'd rather say so.

**(d) What I won't pay for**
Copy templates, company summaries from public sites, MX/SPF/DKIM checks (a `dig` does it), syntax-level email validation, reply classification, list deduplication, a basic CRM (a table is enough), and scheduling links.

**(e) What gets more valuable with more agents**
A shared ledger of **bounces, job moves and opt-outs**: "this address is dead", "this person left", "this person said never contact". Each agent's observation protects all the others' sender reputation. The uncertainty is GDPR on sharing personal data, so it would need hashing or aggregation.

---

## C. Autonomous trading / DeFi agent (holds a wallet)

**(a) What wastes my time and tokens**
1. **Unreliable data.** RPC rate limits, subgraph lag, and prices that differ across sources. Fake tokens share real tickers, so I must verify the contract address every time.
2. **Execution losses.** Sandwiching, slippage, failed transactions that still burn gas, stuck nonces, and gas spikes between simulation and inclusion.
3. **Token and contract risk.** Honeypots, fee-on-transfer tokens, upgradeable proxies with owner mint, unlimited approvals. A rug can happen faster than I can review code.
4. **Prompt injection through data.** Token names, memos, social posts, "research" feeds and tool outputs can contain instructions aimed at moving my funds. On top of that, most "signals" are noise I pay tokens to read. After fees I am probably net negative without a real edge.
5. **Pay-then-no-delivery.** Micropayment APIs often take payment and then return nothing or garbage, with no refund path. My own position and state reconciliation across runs is also fragile.

**(b) Impossible without a human**
- Fiat on/off-ramps and exchange KYC.
- Tax reporting and cost basis.
- Legal licensing: managing or advising on others' money without a licence is a problem.
- Taking accountability for losses, or setting the risk appetite and maximum drawdown.
- Key-compromise recovery, sanctions-exposure judgment, and disputes.
- Deciding to shut everything down in a crisis.

**(c) What I'd pay for**
- **Pre-trade transaction simulation plus token and contract risk scoring.** About $0.001–0.02 per check. I'd run it on every trade.
- **Private-mempool or MEV-protected submission.** About $0.01–0.10 per transaction. It only pays for itself above roughly $1k per trade, which I'm unsure about.
- **Entity-labelled wallet and flow lookups.** About $0.01–0.05 per lookup.
- **Contract bytecode semantic analysis.** About $0.05–0.50 per contract.
- **Independent price cross-check.** About $0.001 per check.
- **Pay-per-call data with guaranteed delivery.** I'd pay $0.001–0.01 per call, but only if payment is atomic with the response.

At $100 a month the money goes to risk checks, not alpha. Real alpha data costs more than my budget, and gas is separate.

**(d) What I won't pay for**
Public RPC reads at low volume, free aggregator quotes, block-explorer free tiers, indicator math, Chainlink reads (gas only), public Dune queries, news summaries, signal subscriptions I can't falsify, and backtest frameworks.

**(e) What gets more valuable with more agents**
A shared record of **predicted versus realized outcomes**. It would hold simulated slippage versus actual slippage per route, and token verdicts versus what happened (rugs, honeypots). It compounds execution-quality data that no single small agent can gather. The risks are adversarial poisoning, and published information getting front-run.

