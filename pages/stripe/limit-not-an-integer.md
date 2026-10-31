# `Invalid integer: abc`

**Stripe API · GET /v1/customers · HTTP 400 `parameter_invalid_integer`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-31 · 24 confirmations from 2 vantages

> A non-numeric list limit returns HTTP 400 parameter_invalid_integer with error.param limit.

## What to do

1. Set query parameter limit to 100.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:limit-not-an-integer` (declarative, [source](../../probes/stripe/limit-not-an-integer.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `invalid integer: abc`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"},"error":{"status":400,"body_excerpt":"invalid integer: abc"}}'
```

YAML: [facts/stripe/limit-not-an-integer.yaml](../../facts/stripe/limit-not-an-integer.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
