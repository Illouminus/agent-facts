# `No such customer: 'cus_apifactsnosuch'`

**Stripe API · GET /v1/customers/{id} · HTTP 404 `resource_missing`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-31 · 125 confirmations from 2 vantages

> Retrieving a customer id that does not exist returns HTTP 404 resource_missing with error.param id and the id quoted in the message.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:customer-not-found` (declarative, [source](../../probes/stripe/customer-not-found.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `no such customer: 'cus_apifactsnosuch'`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers/{id}"},"error":{"status":404,"body_excerpt":"no such customer: '\''cus_apifactsnosuch'\''"}}'
```

YAML: [facts/stripe/customer-not-found.yaml](../../facts/stripe/customer-not-found.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
