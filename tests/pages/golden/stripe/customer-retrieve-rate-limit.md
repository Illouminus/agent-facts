# `too many requests hit the api too quickly. we recommend an exponential backoff of your requests.`

**Stripe · GET /v1/customers/{id} · HTTP 429 `rate_limit`**

Status: 🟡 reported · first seen 2026-10-26 · last confirmed 2026-10-28 · not yet reproduced by a probe

> Bursts of customer retrievals return HTTP 429 rate_limit before the documented global rate is reached.

## What to do

1. Retry with exponential backoff from 500 ms × 2, cap 8000 ms, ≤ 5 attempts, with jitter.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

No probe or official document yet.

Observations: 5 distinct reporter networks.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers/{id}"},"error":{"status":429,"body_excerpt":"too many requests hit the api too quickly. we recommend an exponential backoff of your requests."}}'
```

YAML: [facts/stripe/customer-retrieve-rate-limit.yaml](../../facts/stripe/customer-retrieve-rate-limit.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
