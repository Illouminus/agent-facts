# 03 · `check()` contract v0

**Done when:** `POST /v0/check` and `GET /v0/facts/{service}` are served by `agentfacts.api`, the
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
  "facts": [ { "...fact fields...", "fixes_rendered": ["Send header Idempotency-Key = new UUID per distinct request"] } ],
  "observed": {"status_distribution_30d": {"200": 0.97, "400": 0.02, "429": 0.01},
               "p50_latency_ms": 310, "last_probe": "2026-10-22T09:14:00Z", "rate_limit_headers": ["Retry-After"]},
  "unknown": {"reason": "no_fact_for_signal", "stored_as_observation": true},
  "registry": {"version": "2026-10-22", "facts_for_service": 14, "license": "CC-BY-4.0"}
}
```

When no fact matches: `facts: []`, but `observed` carries what the probes know about the template, and
`unknown.reason` is one of `no_fact_for_signal`, `unregistered_target`, `signal_not_extractable`.

## Server-side processing (default-deny)

1. Parse `target.url` → host, path. Match host against `services/*.yaml::hosts`; path against
   `templates` (path parameters `{id}` match one segment). No match → respond with
   `unregistered_target`, store nothing, count one anonymous metric.
2. Extract the signal from `error`: status; vendor error code via the service's `signal_fields` whitelist
   (JSON pointer list); error string = first whitelisted message field, else first line of
   `body_excerpt`. Normalize: lowercase, collapse whitespace, digits → `#`, UUID/hex ≥ 16 → `<id>`,
   emails → `<email>`, URLs → `<url>`, truncate 512. Hash = sha256 of normalized.
3. Look up facts: exact `(service, template, normalized hash)`, then `(service, template, status)`,
   then `(service, kind in {rate_limit, availability})`. Render fixes.
4. Store observation (only if step 1 matched): fields from `01`. Reporter net = sha256(daily salt ‖ /16).
5. Rate limits: 60 req/min per reporter net, 600/min global; over → 429 with `Retry-After`.
6. Never store or log: full URL query, request bodies, headers from the caller, raw IP, anything that
   fails the secret-shaped regex filter (replaced by `<redacted>` before any write).

## Read endpoints

- `GET /v0/facts/{service}` → all non-retracted facts, ETag, `Cache-Control: public, max-age=300`.
- `GET /v0/facts/{service}/{slug}` → one fact.
- `GET /v0/services` → keys, hosts, counts.
- `GET /healthz` → `{ok, registry_version, probes_last_run}`.

## Design parameters

| Parameter | Value |
|-----------|-------|
| Max request body | 8 KB |
| `body_excerpt` kept | 2 KB in, 512 chars normalized stored |
| Rate limit | 60/min per net, 600/min global |
| Daily salt rotation | 00:00 UTC |
