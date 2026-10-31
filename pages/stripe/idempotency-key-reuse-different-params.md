# `Keys for idempotent requests can only be used with the same parameters they were first used with. Try using a key other than '3f1e9c2a-7b4d-4e8f-9a6c-1d2b3c4d5e6f' if you meant to execute a different request.`

**Stripe API · POST /v1/payment_intents · HTTP 400 `idempotency_error`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-30 · 16 confirmations from 2 vantages

> Reusing an Idempotency-Key with a different request body returns HTTP 400 with error type idempotency_error.

## What to do

1. Send header Idempotency-Key = new UUID per distinct request.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:idempotency-key-reuse` (declarative, [source](../../probes/stripe/idempotency-key-reuse.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `keys for idempotent requests can only be used with the same parameters they were first used with. try using a key other than '<id>' if you meant to execute a different request.`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"keys for idempotent requests can only be used with the same parameters they were first used with. try using a key other than '\''<id>'\'' if you meant to execute a different request."}}'
```

YAML: [facts/stripe/idempotency-key-reuse-different-params.yaml](../../facts/stripe/idempotency-key-reuse-different-params.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
