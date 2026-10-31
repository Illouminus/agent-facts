# ``The `payment_method_types` parameter is no longer supported. Payment methods are now managed from your Dashboard settings (https://dashboard.stripe.com/settings/payment_methods). For migration guidance, see https://docs.stripe.com/payments/payment-methods/dynamic-payment-methods.``

**Stripe API · POST /v1/payment_intents · HTTP 400**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-30 · 16 confirmations from 2 vantages

> On API version 2026-09-30.endive, creating a PaymentIntent with payment_method_types returns HTTP 400 (no error code, parameter no longer supported); the same request on version 2024-06-20 succeeds.

## What to do

1. Omit body parameter payment_method_types.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:payment-method-types-removed` (declarative, [source](../../probes/stripe/payment-method-types-removed.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): ``the `payment_method_types` parameter is no longer supported. payment methods are now managed from your dashboard settings (<url>). for migration guidance, see <url>``

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"the `payment_method_types` parameter is no longer supported. payment methods are now managed from your dashboard settings (<url>). for migration guidance, see <url>"}}'
```

YAML: [facts/stripe/payment-method-types-removed.yaml](../../facts/stripe/payment-method-types-removed.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
