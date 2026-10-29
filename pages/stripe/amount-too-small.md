# `amount must convert to at least ## cents. $#.## converts to approximately €#.##.`

**Stripe API · POST /v1/payment_intents · HTTP 400 `amount_too_small`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-28 · 12 confirmations from 2 vantages

> A PaymentIntent with amount 10 and currency usd (10 cents) returns HTTP 400 amount_too_small: the amount must convert to at least 50 cents; on a test account settling in EUR the message also gives the converted amount (€0.09).

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:amount-too-small` (declarative, [source](../../probes/stripe/amount-too-small.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"amount must convert to at least ## cents. $#.## converts to approximately €#.##."}}'
```

YAML: [facts/stripe/amount-too-small.yaml](../../facts/stripe/amount-too-small.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
