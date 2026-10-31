# Stripe API

Hosts: `api.stripe.com` · 26 facts

## Error meanings

- ✅ verified:server:sandbox · [`Amount must convert to at least 50 cents. $0.10 converts to approximately €0.09.`](amount-too-small.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`Your card was declined.`](card-declined-generic.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`Your card has expired.`](card-expired.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`Your card's security code is incorrect.`](card-incorrect-cvc.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`Your card has insufficient funds. Use a different payment method to complete this purchase.`](card-insufficient-funds.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`Your card was declined.`](card-lost-generic-message.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`No such customer: 'cus_apifactsnosuch'`](customer-not-found.md) · GET /v1/customers/{id} · env sandbox
- ✅ verified:server:sandbox · [`This property cannot be expanded (data.agent_facts).`](expand-not-expandable.md) · GET /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`Keys for idempotent requests can only be used for the same endpoint they were first used for ('/v1/payment_intents' vs '/v1/customers'). Try using a key other than '3f1e9c2a-7b4d-4e8f-9a6c-1d2b3c4d5e6f' if you meant to execute a different request."`](idempotency-key-other-endpoint.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`Keys for idempotent requests can only be used with the same parameters they were first used with. Try using a key other than '3f1e9c2a-7b4d-4e8f-9a6c-1d2b3c4d5e6f' if you meant to execute a different request.`](idempotency-key-reuse-different-params.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`Idempotent key length is 256 characters long, which is outside accepted lengths. Idempotent Keys must be 1-255 characters long. If you're looking for a decent generator, try using a UUID defined by IETF RFC 4122.`](idempotency-key-too-long.md) · POST /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`Invalid Stripe API version: 2099-01-01`](invalid-api-version-400.md) · GET /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`Invalid integer: abc`](limit-not-an-integer.md) · GET /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`Received unknown parameter: agent_facts_unknown`](parameter-unknown.md) · POST /v1/customers · env sandbox

## Rate limits

- 🔵 official · [A rate-limited request returns HTTP 429 with a Stripe-Rate-Limited-Reason header (global-rate, endpoint-rate, global-concurrency, endpoint-concurrency or resource-specific); a 429 without it is not a rate limit, e.g. lock_timeout.](rate-limited-reason-header.md) · GET /v1/customers · env sandbox

## Breaking changes

- ✅ verified:server:sandbox · [``The `payment_method_types` parameter is no longer supported. Payment methods are now managed from your Dashboard settings (https://dashboard.stripe.com/settings/payment_methods). For migration guidance, see https://docs.stripe.com/payments/payment-methods/dynamic-payment-methods.``](payment-method-types-removed.md) · POST /v1/payment_intents · env sandbox

## Silent behavior

- ✅ verified:server:sandbox · [Retrieving a deleted customer returns HTTP 200 with a stub object (id, object, deleted: true) instead of 404; fields such as email are absent.](deleted-customer-returns-200.md) · GET /v1/customers/{id} · env sandbox
- ✅ verified:server:sandbox · [`Amount must convert to at least 50 cents. $0.10 converts to approximately €0.09.`](execution-errors-are-replayed.md) · POST /v1/payment_intents · env sandbox
- 🔵 official · [Idempotency keys may be removed once they are at least 24 hours old; a key reused after removal starts a new request instead of replaying the saved response.](idempotency-keys-pruned-after-24h.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [Repeating a POST with the same Idempotency-Key and the same body returns the saved first response with the header Idempotent-Replayed: true, which the first response does not carry.](idempotent-replay-header.md) · POST /v1/customers · env sandbox
- ✅ verified:server:sandbox · [A POST sent without an Idempotency-Key header is answered with an Idempotency-Key response header holding a UUID chosen by Stripe; a GET gets no such header.](server-assigned-idempotency-key.md) · POST /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`Received unknown parameter: agent_facts_unknown`](validation-errors-are-not-replayed.md) · POST /v1/customers · env sandbox

## Auth quirks

- ✅ verified:server:sandbox · [`You did not provide an API key. You need to provide your API key in the Authorization header, using Bearer auth (e.g. 'Authorization: Bearer YOUR_SECRET_KEY'). See https://stripe.com/docs/api#authentication for details, or we can help at https://support.stripe.com/.`](missing-api-key-401.md) · GET /v1/customers · env sandbox

## Pagination

- ✅ verified:server:sandbox · [GET /v1/customers?limit=0, outside the documented range 1-100, is not rejected: it returns a list holding one object, with has_more: true.](limit-zero-returns-one.md) · GET /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`No such customer: 'cus_apifactsnosuch'`](starting-after-missing-object.md) · GET /v1/customers · env sandbox

## Sandbox divergence

- 🔵 official · [The global API rate limit per account is 25 requests per second in a sandbox against 100 in live mode; most individual endpoints are limited to 25 requests per second.](sandbox-rate-limit-lower.md) · GET /v1/customers · env sandbox

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
