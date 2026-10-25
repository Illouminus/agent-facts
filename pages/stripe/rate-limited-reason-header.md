# A rate-limited request returns HTTP 429 with a Stripe-Rate-Limited-Reason header (global-rate, endpoint-rate, global-concurrency, endpoint-concurrency or resource-specific); a 429 without it is not a rate limit, e.g. lock_timeout.

**Stripe API · GET /v1/customers · HTTP 429**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 1000 ms × 2, cap 32000 ms, ≤ 5 attempts, with jitter.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.stripe.com/rate-limits>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"},"error":{"status":429}}'
```

YAML: [facts/stripe/rate-limited-reason-header.yaml](../../facts/stripe/rate-limited-reason-header.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
