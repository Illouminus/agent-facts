# `keys for idempotent requests can only be used with the same parameters they were first used with`

**Stripe · POST /v1/payment_intents · SDK `stripe` (pypi) `>=7,<13` · HTTP 400 `idempotency_error`**

Status: ✅ verified:server:sandbox · first seen 2026-10-23 · last confirmed 2026-10-29 · 4 confirmations from 1 vantage

> Reusing an Idempotency-Key with a different request body returns HTTP 400 idempotency_error for 24 hours after the first request.

## What to do

1. Set parameter Idempotency-Key to new UUID per distinct request.

## Dimensions

env: sandbox · plan: any · region: any · account_state: test_mode · also seen: [prod/any](idempotency-key-reuse-different-params.md) (verified 2026-10-22)

## Evidence

Probe `af:stripe:probe:idempotency-key-reuse` (declarative, [source](../../probes/stripe/idempotency-key-reuse.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"keys for idempotent requests can only be used with the same parameters they were first used with"}}'
```

YAML: [facts/stripe/idempotency-key-reuse-different-params-sandbox.yaml](../../facts/stripe/idempotency-key-reuse-different-params-sandbox.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
