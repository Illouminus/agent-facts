# `keys for idempotent requests can only be used for the same endpoint they were first used for ('/v#/payment_intents' vs '/v#/customers'). try using a key other than '<id>' if you meant to execute a different request."`

**Stripe API · POST /v1/payment_intents · HTTP 400 `idempotency_error`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-25 · 3 confirmations from 2 vantages

> An Idempotency-Key first used on one endpoint returns HTTP 400 idempotency_error when sent to another endpoint; the message names the current path, then the original one.

## What to do

1. Send header Idempotency-Key = new UUID per distinct request.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:idempotency-key-other-endpoint` (declarative, [source](../../probes/stripe/idempotency-key-other-endpoint.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"keys for idempotent requests can only be used for the same endpoint they were first used for ('\''/v#/payment_intents'\'' vs '\''/v#/customers'\''). try using a key other than '\''<id>'\'' if you meant to execute a different request.\""}}'
```

YAML: [facts/stripe/idempotency-key-other-endpoint.yaml](../../facts/stripe/idempotency-key-other-endpoint.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
