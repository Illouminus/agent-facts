# Stripe

Hosts: `api.stripe.com` · 5 facts

## Error meanings

- ✅ verified:server:prod · [`Keys for idempotent requests can only be used with the same parameters they were first used with.`](idempotency-key-reuse-different-params.md) · POST /v1/payment_intents · env prod
- ✅ verified:server:sandbox · [`Keys for idempotent requests can only be used with the same parameters they were first used with.`](idempotency-key-reuse-different-params-sandbox.md) · POST /v1/payment_intents · env sandbox
- ⛔ retracted · [`Amount must be at least $0.50 usd`](amount-too-small.md)

## Rate limits

- 🟡 reported · [`Too many requests hit the API too quickly. We recommend an exponential backoff of your requests.`](customer-retrieve-rate-limit.md) · GET /v1/customers/{id} · env prod

## Silent behavior

- ⚪ stale · [Retrieving a deleted customer returns HTTP 200 with deleted set to true instead of HTTP 404.](deleted-customer-returns-200.md) · GET /v1/customers/{id} · env sandbox

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
