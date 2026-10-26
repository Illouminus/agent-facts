# `your card has insufficient funds. use a different payment method to complete this purchase.`

**Stripe API · POST /v1/payment_intents · HTTP 402 `card_declined`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-25 · 6 confirmations from 2 vantages

> Confirming a PaymentIntent with test payment method pm_card_chargeDeclinedInsufficientFunds returns HTTP 402 card_error with code card_declined, decline_code insufficient_funds and advice_code try_again_later.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:card-insufficient-funds` (declarative, [source](../../probes/stripe/card-insufficient-funds.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":402,"body_excerpt":"your card has insufficient funds. use a different payment method to complete this purchase."}}'
```

YAML: [facts/stripe/card-insufficient-funds.yaml](../../facts/stripe/card-insufficient-funds.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
