# `your card has expired.`

**Stripe API · POST /v1/payment_intents · HTTP 402 `expired_card`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 4 confirmations from 2 vantages

> Confirming a PaymentIntent with test payment method pm_card_chargeDeclinedExpiredCard returns HTTP 402 card_error with code expired_card, decline_code expired_card and advice_code confirm_card_data; error.param is exp_month.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:card-expired` (declarative, [source](../../probes/stripe/card-expired.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":402,"body_excerpt":"your card has expired."}}'
```

YAML: [facts/stripe/card-expired.yaml](../../facts/stripe/card-expired.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
