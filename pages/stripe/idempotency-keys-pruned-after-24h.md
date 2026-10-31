# Idempotency keys may be removed once they are at least 24 hours old; a key reused after removal starts a new request instead of replaying the saved response.

**Stripe API · POST /v1/payment_intents**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Send header Idempotency-Key = new UUID per distinct request.

## In your code

Fix 1:

```python
import uuid
headers["Idempotency-Key"] = str(uuid.uuid4())  # a new value per distinct request; reuse it only to retry
```

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.stripe.com/api/idempotent_requests>

Observations: none from reporters yet.

## Related errors

- [`Amount must convert to at least 50 cents. $0.10 converts to approximately €0.09.`](amount-too-small.md) · POST /v1/payment_intents · HTTP 400 `amount_too_small`
- [`Your card was declined.`](card-declined-generic.md) · POST /v1/payment_intents · HTTP 402 `card_declined`
- [`Your card has expired.`](card-expired.md) · POST /v1/payment_intents · HTTP 402 `expired_card`
- [`Your card's security code is incorrect.`](card-incorrect-cvc.md) · POST /v1/payment_intents · HTTP 402 `incorrect_cvc`
- [`Your card has insufficient funds. Use a different payment method to complete this purchase.`](card-insufficient-funds.md) · POST /v1/payment_intents · HTTP 402 `card_declined`
- [`Your card was declined.`](card-lost-generic-message.md) · POST /v1/payment_intents · HTTP 402 `card_declined`

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"}}'
```

YAML: [facts/stripe/idempotency-keys-pruned-after-24h.yaml](../../facts/stripe/idempotency-keys-pruned-after-24h.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
