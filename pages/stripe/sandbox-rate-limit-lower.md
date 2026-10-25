# The global API rate limit per account is 25 requests per second in a sandbox against 100 in live mode; most individual endpoints are limited to 25 requests per second.

**Stripe API · GET /v1/customers**

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
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"}}'
```

YAML: [facts/stripe/sandbox-rate-limit-lower.yaml](../../facts/stripe/sandbox-rate-limit-lower.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
