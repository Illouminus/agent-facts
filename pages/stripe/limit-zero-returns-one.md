# GET /v1/customers?limit=0, outside the documented range 1-100, is not rejected: it returns a list holding one object, with has_more: true.

**Stripe API · GET /v1/customers · HTTP 200**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-28 · 15 confirmations from 2 vantages

## What to do

1. Paginate by id via starting_after, ≤ 100 per page.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:limit-zero-returns-one` (declarative, [source](../../probes/stripe/limit-zero-returns-one.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"},"error":{"status":200}}'
```

YAML: [facts/stripe/limit-zero-returns-one.yaml](../../facts/stripe/limit-zero-returns-one.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
