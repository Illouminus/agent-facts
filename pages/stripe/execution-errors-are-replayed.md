# `amount must convert to at least ## cents. $#.## converts to approximately €#.##.`

**Stripe API · POST /v1/payment_intents · HTTP 400 `amount_too_small`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 1 confirmation from 1 vantage

> A 400 returned after the endpoint began executing, such as amount_too_small, is saved under its Idempotency-Key: a retry with the same key returns the same error with Idempotent-Replayed: true, even if the cause has been fixed elsewhere.

## What to do

1. Send header Idempotency-Key = new UUID per distinct request.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:replayed-execution-error` (declarative, [source](../../probes/stripe/replayed-execution-error.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"amount must convert to at least ## cents. $#.## converts to approximately €#.##."}}'
```

YAML: [facts/stripe/execution-errors-are-replayed.yaml](../../facts/stripe/execution-errors-are-replayed.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
