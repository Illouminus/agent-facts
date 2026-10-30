# `your card was declined.`

**Stripe API · POST /v1/payment_intents · HTTP 402 `card_declined`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-30 · 15 confirmations from 2 vantages

> Confirming a PaymentIntent with test payment method pm_card_chargeDeclined returns HTTP 402 card_error with code card_declined, decline_code generic_decline and advice_code try_again_later.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:card-declined-generic` (declarative, [source](../../probes/stripe/card-declined-generic.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":402,"body_excerpt":"your card was declined."}}'
```

YAML: [facts/stripe/card-declined-generic.yaml](../../facts/stripe/card-declined-generic.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
