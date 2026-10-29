# `your card's security code is incorrect.`

**Stripe API · POST /v1/payment_intents · HTTP 402 `incorrect_cvc`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-28 · 12 confirmations from 2 vantages

> Confirming a PaymentIntent with test payment method pm_card_chargeDeclinedIncorrectCvc returns HTTP 402 card_error with code incorrect_cvc, decline_code incorrect_cvc and advice_code confirm_card_data; error.param is cvc.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:card-incorrect-cvc` (declarative, [source](../../probes/stripe/card-incorrect-cvc.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":402,"body_excerpt":"your card'\''s security code is incorrect."}}'
```

YAML: [facts/stripe/card-incorrect-cvc.yaml](../../facts/stripe/card-incorrect-cvc.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
