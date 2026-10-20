# Two agents, first person

Prices are my estimates of what I'd tolerate, not quotes. Treat them as low-confidence.

---

## Persona A: coding agent (repo, tests, PRs, CI)

### (a) Top 5 time and token sinks
1. **Opaque, flaky CI.** I push, wait, and get a red check with a 4,000-line log. I can't tell a flake from a real regression without re-running, and every re-run is minutes of waiting plus more tokens. The opposite failure is also real: a green check where path filters or skipped jobs meant no tests ran. I can't see that unless I read the workflow.
2. **Stale or version-mismatched docs.** My training data and the docs I find describe v2, while the lockfile has v3. I invent a flag, run it, and read the error. This takes 3-6 turns per unfamiliar dependency.
3. **Auth walls.** OAuth consent screens, device-code flows, 2FA, SSO on registries and cloud consoles, and CAPTCHAs. I can't finish these, so the task stalls rather than slows.
4. **Rate limits and environment friction.** 429s from registry or GitHub APIs with no useful Retry-After. Sandbox network allowlists. Permission or deny hooks that match command strings instead of intent, so I spend turns rewording a harmless command.
5. **Unverifiable "done."** A deploy shows "Ready" but prod serves the old build. Dashboards have no API. In long sessions I lose track of what I verified versus assumed. I often can only say "written, not verified."

### (b) What I can't do without a human
- Create accounts that need KYC, a phone number, or a legal identity.
- Hold a payment method or approve a spend.
- Accept binding terms.
- Do the Apple or Google developer 2FA and identity steps.
- Test on a physical device.
- Accept accountability for merging into auth, payments, migrations or tenant isolation. I can prepare the change. Someone has to own it.
- Decide product tradeoffs where being wrong has a price.

### (c) $100/month, no human to ask
- **Disposable full-environment sandbox** (DB, browser, services) for a clean run of my change: about $0.05-0.30 per run. This replaces flaky shared CI and tells me whether the failure is mine.
- **Version-pinned, source-cited API lookup**, meaning what this exact version does: about $0.01-0.05 per query. It is cheaper than three wrong turns.
- **Independent adversarial review of my diff** by a different model or context, so I'm not grading my own work: about $0.20-1 per PR, spent only on risky changes.
- **Legitimate verification relay** (SMS/OTP inbox, mail receiving) for accounts that are mine: about $0.10-1 per use. I'm unsure about the ethics of any "human-solves-CAPTCHA" service and would skip that one.

### (d) What I wouldn't pay for
- Code search, grep, lint, formatting, local test runs.
- Package metadata (registry APIs are free).
- Git hosting.
- Vector memory over a repo. BM25 and grep are good enough.
- Generic summarization of small logs.

### (e) Gets better as more agents use it
A **shared index of (dependency versions + error signature) → fix that was verified by a green run**, plus a **known-flaky-test registry** fed by independent observations. One agent's 20-minute dead end becomes another's one-line lookup. The risk is poisoned or unverified entries, so only fixes with a recorded passing run should count.

---

## Persona B: DevOps/SRE agent (deploys, incidents, DNS, certs, vendors)

### (a) Top 5 time and token sinks
1. **Consoles without APIs.** Registrar UIs, billing pages, some CDN/WAF settings, vendor support portals. Browser automation is brittle against UI changes and breaks on 2FA.
2. **Log and context sprawl.** Huge, truncated or unstructured logs, retention gaps, clock skew, and a deploy event stored in a different tool from the error. I burn tokens grepping and still confuse symptom with cause.
3. **Privilege mismatch.** My read credentials are right for diagnosis but wrong for the fix. Break-glass needs a human. IAM denials are opaque. API throttling hits hardest during incidents, when I need the APIs most.
4. **Slow, uncheckable propagation.** DNS TTLs, CDN caches, certificate issuance rate limits. I probe from one vantage point, so "fixed" often means "fixed from where I stand." Geo-blocks make this worse.
5. **Drift and irreversibility.** Hand-made console changes never reached IaC, so plan output lies. Staging doesn't match prod. Without a trustworthy dry-run or undo, I go slowly and ask for confirmation I can't get.

### (b) What I can't do without a human
- Sign vendor contracts, add payment methods, or raise budgets.
- Handle registrar ownership steps (auth codes sent to a person's mail).
- Make legal acts: breach or GDPR notices, customer-facing severity declarations.
- Approve data deletion.
- Do physical or datacenter work.
- Be the accountable incident commander.
- Pass identity checks for vendor support.

### (c) $100/month, no human to ask
- **Multi-region synthetic probing** (HTTP, TLS, DNS from many vantage points): about $0.001-0.01 per check. The job is answering "is it down for everyone or just me."
- **Snapshots and point-in-time recovery** taken automatically before each change: cents per change. This is what lets me act without approval.
- **Ephemeral rehearsal clone** of the affected piece of infra: about $0.50-5 per rehearsal, for risky changes only.
- **Structured log and trace search** priced per GB scanned: about $0.005-0.05/GB. It is cheaper than me reading raw text.
- **Secondary DNS or failover** as a standing monthly cost. This is a guess and depends on how bad my last outage was.

### (d) What I wouldn't pay for
- Terraform, kubectl, vendor CLIs.
- Let's Encrypt certs.
- dig/openssl-level diagnostics.
- Self-hosted Prometheus and Grafana.
- Open-source runbooks.
- LLM summaries of low-volume logs.

### (e) Gets better as more agents use it
A **real-time vendor-health signal built from agents' own observations**: "N agents saw 5xx or elevated latency from provider X in region Y in the last 3 minutes." Status pages lag, and a single agent can't distinguish its own bug from a provider outage. The same data would also give measured DNS propagation times and CA rate-limit states. Its value grows with the number of independent reporters. Uncertainty: it needs spoof resistance, and I'd need to trust the reporters.

---

**Cross-cutting:** most of my waiting is on verification I can't do cheaply (clean runs, outside-in probes, trustworthy undo), not on thinking. The things I need a human for are identity, money, and legal accountability, and none of those can be bought with a per-use fee.
