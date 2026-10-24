# Stripe API

Hosts: `api.stripe.com` · 26 facts

## Error meanings

- ✅ verified:server:sandbox · [`amount must convert to at least ## cents. $#.## converts to approximately €#.##.`](amount-too-small.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`your card was declined.`](card-declined-generic.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`your card has expired.`](card-expired.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`your card's security code is incorrect.`](card-incorrect-cvc.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`your card has insufficient funds. use a different payment method to complete this purchase.`](card-insufficient-funds.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`your card was declined.`](card-lost-generic-message.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`no such customer: 'cus_agentfactsnosuch'`](customer-not-found.md) · GET /v1/customers/{id} · env sandbox
- ✅ verified:server:sandbox · [`this property cannot be expanded (data.agent_facts).`](expand-not-expandable.md) · GET /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`keys for idempotent requests can only be used for the same endpoint they were first used for ('/v#/payment_intents' vs '/v#/customers'). try using a key other than '<id>' if you meant to execute a different request."`](idempotency-key-other-endpoint.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`keys for idempotent requests can only be used with the same parameters they were first used with. try using a key other than '<id>' if you meant to execute a different request.`](idempotency-key-reuse-different-params.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [`idempotent key length is ### characters long, which is outside accepted lengths. idempotent keys must be #-### characters long. if you're looking for a decent generator, try using a uuid defined by ietf rfc ####.`](idempotency-key-too-long.md) · POST /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`invalid stripe api version: ####-##-##`](invalid-api-version-400.md) · GET /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`invalid integer: abc`](limit-not-an-integer.md) · GET /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`received unknown parameter: agent_facts_unknown`](parameter-unknown.md) · POST /v1/customers · env sandbox

## Rate limits

- 🔵 official · [A rate-limited request returns HTTP 429 with a Stripe-Rate-Limited-Reason header (global-rate, endpoint-rate, global-concurrency, endpoint-concurrency or resource-specific); a 429 without it is not a rate limit, e.g. lock_timeout.](rate-limited-reason-header.md) · GET /v1/customers · env sandbox

## Breaking changes

- ✅ verified:server:sandbox · [``the `payment_method_types` parameter is no longer supported. payment methods are now managed from your dashboard settings (<url>). for migration guidance, see <url>``](payment-method-types-removed.md) · POST /v1/payment_intents · env sandbox

## Silent behavior

- ✅ verified:server:sandbox · [Retrieving a deleted customer returns HTTP 200 with a stub object (id, object, deleted: true) instead of 404; fields such as email are absent.](deleted-customer-returns-200.md) · GET /v1/customers/{id} · env sandbox
- ✅ verified:server:sandbox · [`amount must convert to at least ## cents. $#.## converts to approximately €#.##.`](execution-errors-are-replayed.md) · POST /v1/payment_intents · env sandbox
- 🔵 official · [Idempotency keys may be removed once they are at least 24 hours old; a key reused after removal starts a new request instead of replaying the saved response.](idempotency-keys-pruned-after-24h.md) · POST /v1/payment_intents · env sandbox
- ✅ verified:server:sandbox · [Repeating a POST with the same Idempotency-Key and the same body returns the saved first response with the header Idempotent-Replayed: true, which the first response does not carry.](idempotent-replay-header.md) · POST /v1/customers · env sandbox
- ✅ verified:server:sandbox · [A POST sent without an Idempotency-Key header is answered with an Idempotency-Key response header holding a UUID chosen by Stripe; a GET gets no such header.](server-assigned-idempotency-key.md) · POST /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`received unknown parameter: agent_facts_unknown`](validation-errors-are-not-replayed.md) · POST /v1/customers · env sandbox

## Auth quirks

- ✅ verified:server:sandbox · [`you did not provide an api key. you need to provide your api key in the authorization header, using bearer auth (e.g. 'authorization: <redacted>'). see <url> for details, or we can help at <url>`](missing-api-key-401.md) · GET /v1/customers · env sandbox

## Pagination

- ✅ verified:server:sandbox · [GET /v1/customers?limit=0, outside the documented range 1-100, is not rejected: it returns a list holding one object, with has_more: true.](limit-zero-returns-one.md) · GET /v1/customers · env sandbox
- ✅ verified:server:sandbox · [`no such customer: 'cus_agentfactsnosuch'`](starting-after-missing-object.md) · GET /v1/customers · env sandbox

## Sandbox divergence

- 🔵 official · [The global API rate limit per account is 25 requests per second in a sandbox against 100 in live mode; most individual endpoints are limited to 25 requests per second.](sandbox-rate-limit-lower.md) · GET /v1/customers · env sandbox

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
