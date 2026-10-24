# `your card was declined.`

**Stripe API · POST /v1/payment_intents · HTTP 402 `card_declined`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 2 confirmations from 1 vantage

> For test payment method pm_card_visa_chargeDeclinedLostCard the 402 message is the generic "Your card was declined."; the reason is only in decline_code lost_card, with advice_code do_not_try_again.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:card-lost` (declarative, [source](../../probes/stripe/card-lost.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":402,"body_excerpt":"your card was declined."}}'
```

YAML: [facts/stripe/card-lost-generic-message.yaml](../../facts/stripe/card-lost-generic-message.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
