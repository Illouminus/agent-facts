# Repeating a POST with the same Idempotency-Key and the same body returns the saved first response with the header Idempotent-Replayed: true, which the first response does not carry.

**Stripe API · POST /v1/customers · HTTP 200**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 4 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:idempotent-replay` (declarative, [source](../../probes/stripe/idempotent-replay.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/customers"},"error":{"status":200}}'
```

YAML: [facts/stripe/idempotent-replay-header.yaml](../../facts/stripe/idempotent-replay-header.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
