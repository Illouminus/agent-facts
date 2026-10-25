# A POST sent without an Idempotency-Key header is answered with an Idempotency-Key response header holding a UUID chosen by Stripe; a GET gets no such header.

**Stripe API · POST /v1/customers · HTTP 200**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 4 confirmations from 2 vantages

## What to do

1. Send header Idempotency-Key = new UUID per distinct request.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:server-idempotency-key` (declarative, [source](../../probes/stripe/server-idempotency-key.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/customers"},"error":{"status":200}}'
```

YAML: [facts/stripe/server-assigned-idempotency-key.yaml](../../facts/stripe/server-assigned-idempotency-key.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
