# `keys for idempotent requests can only be used with the same parameters they were first used with. try using a key other than '<id>' if you meant to execute a different request.`

**Stripe API · POST /v1/payment_intents · HTTP 400 `idempotency_error`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 2 confirmations from 1 vantage

> Reusing an Idempotency-Key with a different request body returns HTTP 400 with error type idempotency_error.

## What to do

1. Send header Idempotency-Key = new UUID per distinct request.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:idempotency-key-reuse` (declarative, [source](../../probes/stripe/idempotency-key-reuse.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"keys for idempotent requests can only be used with the same parameters they were first used with. try using a key other than '\''<id>'\'' if you meant to execute a different request."}}'
```

YAML: [facts/stripe/idempotency-key-reuse-different-params.yaml](../../facts/stripe/idempotency-key-reuse-different-params.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
