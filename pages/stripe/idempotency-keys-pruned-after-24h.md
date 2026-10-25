# Idempotency keys may be removed once they are at least 24 hours old; a key reused after removal starts a new request instead of replaying the saved response.

**Stripe API · POST /v1/payment_intents**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Send header Idempotency-Key = new UUID per distinct request.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.stripe.com/api/idempotent_requests>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"}}'
```

YAML: [facts/stripe/idempotency-keys-pruned-after-24h.yaml](../../facts/stripe/idempotency-keys-pruned-after-24h.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
