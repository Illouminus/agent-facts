# `keys for idempotent requests can only be used with the same parameters they were first used with`

**Stripe · POST /v1/payment_intents · SDK `stripe` (pypi) `>=7,<13` · HTTP 400 `idempotency_error`**

Status: ✅ verified:server:prod · first seen 2026-10-22 · last confirmed 2026-10-22 · 1 confirmation from 1 vantage

> Reusing an Idempotency-Key with a different request body returns HTTP 400 idempotency_error for 24 hours after the first request.

## What to do

1. Set parameter Idempotency-Key to new UUID per distinct request.

## Dimensions

env: prod · plan: any · region: any · account_state: any · also seen: [sandbox/test_mode](idempotency-key-reuse-different-params-sandbox.md) (verified 2026-10-29)

## Evidence

Probe `af:stripe:probe:idempotency-key-reuse` (declarative, [source](../../probes/stripe/idempotency-key-reuse.yaml)) · official doc: <https://docs.stripe.com/api/idempotent_requests>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"keys for idempotent requests can only be used with the same parameters they were first used with"}}'
```

YAML: [facts/stripe/idempotency-key-reuse-different-params.yaml](../../facts/stripe/idempotency-key-reuse-different-params.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
