# Retrieving a deleted customer returns HTTP 200 with deleted set to true instead of HTTP 404.

**Stripe · GET /v1/customers/{id} · HTTP 200**

Status: ⚪ stale · first seen 2026-10-21 · last confirmed 2026-10-24 · 3 confirmations from 1 vantage · not reproduced by the last 3 probe runs; not refuted

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:deleted-customer` (declarative, [source](../../probes/stripe/deleted-customer.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers/{id}"},"error":{"status":200}}'
```

YAML: [facts/stripe/deleted-customer-returns-200.yaml](../../facts/stripe/deleted-customer-returns-200.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
