# `idempotent key length is ### characters long, which is outside accepted lengths. idempotent keys must be #-### characters long. if you're looking for a decent generator, try using a uuid defined by ietf rfc ####.`

**Stripe API · POST /v1/customers · HTTP 400 `idempotency_error`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 4 confirmations from 2 vantages

> An Idempotency-Key longer than 255 characters returns HTTP 400 idempotency_error; the message gives the accepted range, 1-255 characters.

## What to do

1. Send header Idempotency-Key = new UUID per distinct request.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:idempotency-key-too-long` (declarative, [source](../../probes/stripe/idempotency-key-too-long.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/customers"},"error":{"status":400,"body_excerpt":"idempotent key length is ### characters long, which is outside accepted lengths. idempotent keys must be #-### characters long. if you'\''re looking for a decent generator, try using a uuid defined by ietf rfc ####."}}'
```

YAML: [facts/stripe/idempotency-key-too-long.yaml](../../facts/stripe/idempotency-key-too-long.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
