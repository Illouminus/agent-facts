# `invalid stripe api version: ####-##-##`

**Stripe API · GET /v1/customers · HTTP 400**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 1 confirmation from 1 vantage

> A Stripe-Version header naming a version that does not exist returns HTTP 400 invalid_request_error without an error code, echoing the version in the message.

## What to do

1. Omit header parameter Stripe-Version.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:invalid-api-version` (declarative, [source](../../probes/stripe/invalid-api-version.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"},"error":{"status":400,"body_excerpt":"invalid stripe api version: ####-##-##"}}'
```

YAML: [facts/stripe/invalid-api-version-400.yaml](../../facts/stripe/invalid-api-version-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
