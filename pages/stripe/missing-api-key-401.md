# `you did not provide an api key. you need to provide your api key in the authorization header, using bearer auth (e.g. 'authorization: <redacted>'). see <url> for details, or we can help at <url>`

**Stripe API · GET /v1/customers · HTTP 401**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 4 confirmations from 2 vantages

> A request without an Authorization header returns HTTP 401 with error type invalid_request_error and no error.code; the message says no API key was provided.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:no-api-key` (declarative, [source](../../probes/stripe/no-api-key.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"},"error":{"status":401,"body_excerpt":"you did not provide an api key. you need to provide your api key in the authorization header, using bearer auth (e.g. '\''authorization: <redacted>'\''). see <url> for details, or we can help at <url>"}}'
```

YAML: [facts/stripe/missing-api-key-401.yaml](../../facts/stripe/missing-api-key-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
