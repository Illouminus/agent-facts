# 03 · `check()` contract v0

**Done when:** `POST /v0/check` and `GET /v0/facts/{service}` are served by `apifacts.api`, the
OpenAPI document is committed at `docs/specs/openapi-v0.json`, the contract tests in
`tests/api/test_check_contract.py` pass, and a request outside registered templates is answered but not
stored (asserted by a test that counts rows).

## Request

```http
POST /v0/check
Content-Type: application/json
User-Agent: <anything>              # classified into: pytest-plugin | jest-plugin | mcp | sdk | other

{
  "target": {"method": "POST", "url": "https://api.stripe.com/v1/payment_intents"},
  "error":  {"status": 400, "body_excerpt": "…first 2 KB of the error body or exception text…"},
  "context": {"sdk": {"package": "stripe", "ecosystem": "pypi", "version": "12.1.0"}, "env_hint": "prod"}
}
```

`target.url` may also be a bare host or a `pypi:stripe@12.1.0` / `npm:@slack/web-api@7.9.0` locator (pre-flight
mode, no error). `error` is optional. Nothing else is accepted: unknown fields → 400 with `unknown_field`.

## Response (never empty)

```json
{
  "service": "stripe",
  "matched_template": {"method": "POST", "path": "/v1/payment_intents"},
  "facts": [ { "...fact fields...", "fixes_rendered": ["Send header Idempotency-Key = new UUID per distinct request"] } ],   // status verified:server:sandbox for this example fact
  "observed": {"status_distribution_30d": {"200": 0.97, "400": 0.02, "429": 0.01},
               "p50_latency_ms": 310, "last_probe": "2026-10-22T09:14:00Z", "rate_limit_headers": ["Retry-After"]},
  "unknown": {"reason": "no_fact_for_signal", "stored_as_observation": true},
  "registry": {"version": "2026-10-22", "facts_for_service": 14, "license": "CC-BY-4.0"}
}
```

When no fact matches: `facts: []`, but `observed` carries what the probes know about the template, and
`unknown.reason` is one of `no_fact_for_signal`, `unregistered_target`, `signal_not_extractable`.

## Server-side processing (default-deny)

1. Parse `target.url` → host, path. Match host against `services/*.yaml::hosts` (exact), or against
   the service's `auth.instance_hosts` — that host or a subdomain of it, e.g. `<org>.my.salesforce.com`
   for `my.salesforce.com` (decision 2026-10-24, D-090); no other subdomain matches. Path against
   `templates` (path parameters `{id}` match one segment). No match → respond with
   `unregistered_target`, store nothing, count one anonymous daily metric; the hostname is kept in that
   metric only when it belongs to the seed candidate list (`apifacts/api/seed_hosts.py`),
   every other host counts as `other` (decision 2026-10-20, Q7).
2. Extract the signal from `error`: status; vendor error code via the service's `signal_fields` whitelist
   (JSON pointer list); error string = first whitelisted message field. An error inside a list, which a
   whitelist name cannot address, is read through the probe runner's own paths
   (`apifacts/schema/error_paths.py`, D-090): message `[0].message` (Salesforce `[{message, errorCode}]`)
   or `.errors[0].message`, code `[0].errorCode` or `.error.errors[0].reason` (Google); a whitelisted field
   wins. A body that is JSON (or truncated JSON) without either yields **no string**, only the status is
   kept (Q4); a non-JSON body falls back to its first line. Normalize: lowercase, collapse whitespace, digits → `#`, UUID/hex ≥ 16 → `<id>`,
   emails → `<email>`, URLs → `<url>`, truncate 512. Hash = sha256 of normalized.
3. Look up facts: exact `(service, template, normalized hash)`, then `(service, template, status)`,
   then `(service, kind in {rate_limit, availability})`. Render fixes.
4. Store observation only if step 1 matched **and** the request carries an `error` — pre-flight calls
   are answered, never stored (Q5). Reporter net = sha256(salt ‖ IPv4 /16 or IPv6 /32) (Q3); the salt
   rotates weekly, Monday 00:00 UTC, so one network keeps one id inside a quorum window (Q6).
   Every answered call (pre-flight too) also adds one to its network's row in `traffic` (period,
   salted net, own/external, calls, stored) — the adoption count of D-092, see `ops/README.md`.
5. Rate limits: 60 req/min per reporter net, 600/min global; over → 429 with `Retry-After`.
6. Never store or log: full URL query, request bodies, headers from the caller, raw IP, anything that
   fails the secret-shaped regex filter (replaced by `<redacted>` before any write).
7. Drop (count, never store) a normalized string that contains a URL outside the service's `hosts` +
   `doc_hosts` (Q1), or a prompt-injection marker: `ignore previous`, `ignore all/any previous`,
   `disregard … previous`, `system:`, `assistant:`, `<|im_start|>`, `[INST]` (Q2).

## Read endpoints

- `GET /v0/facts/{service}` → all non-retracted facts, ETag, `Cache-Control: public, max-age=300`.
- `GET /v0/facts/{service}/{slug}` → one fact.
- `GET /v0/services` → keys, hosts, `instance_hosts` (tenant hosts, D-090; `[]` when none), counts.
- `GET /healthz` → `{ok, registry_version, probes_last_run}`; `probes_last_run` = `started` of the newest
  `pass`/`fail`/`error` line in the runner's `results.jsonl` (`APIFACTS_RESULTS`), `null` if none.

## Readers (every request, site and API)

Caddy keeps no access log and uvicorn runs without one (rule 6), so the only trace of who reads
`apifacts.dev` is a count per (UTC day, User-Agent family, path class, status class)
(`apifacts/api/readers.py`). The family is one token of a fixed, ordered table (GPTBot, ClaudeBot,
ChatGPT-User, …, `script`, `browser`, `unknown`); the path class is the route's shape (`home`,
`fact_page`, `api_check`, …), never the path. Like `reporter_ua_class`, the derived token is all
that is kept of the User-Agent: no raw UA, path, query or IP is stored. The family is what the
caller claims (unverifiable without the IP). Counts are flushed to `var/readers/<YYYY-MM-DD>.json`
every 5 minutes and at shutdown; no db table. Read by `apifacts stats readers` and the weekly digest
(spec 08).

## Design parameters

| Parameter | Value |
|-----------|-------|
| Max request body | 8 KB |
| `body_excerpt` kept | 2 KB in, 512 chars normalized stored |
| Rate limit | 60/min per net, 600/min global |
| Salt rotation | weekly, Monday 00:00 UTC (= quorum window) |
