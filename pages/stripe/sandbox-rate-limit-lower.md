# The global API rate limit per account is 25 requests per second in a sandbox against 100 in live mode; most individual endpoints are limited to 25 requests per second.

**Stripe API · GET /v1/customers**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 1000 ms × 2, cap 32000 ms, ≤ 5 attempts, with jitter.

## In your code

Fix 1:

```python
import random
import time

delay_ms = 1000
for attempt in range(5):
    response = client.send(request)
    if response.is_success:
        break
    time.sleep(random.uniform(0, delay_ms) / 1000)
    delay_ms = min(delay_ms * 2, 32000)
```

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.stripe.com/rate-limits>

Observations: none from reporters yet.

## Related errors

- [`This property cannot be expanded (data.agent_facts).`](expand-not-expandable.md) · GET /v1/customers · HTTP 400
- [`Invalid Stripe API version: 2099-01-01`](invalid-api-version-400.md) · GET /v1/customers · HTTP 400
- [`Invalid integer: abc`](limit-not-an-integer.md) · GET /v1/customers · HTTP 400 `parameter_invalid_integer`
- [`You did not provide an API key. You need to provide your API key in the Authorization header, using Bearer auth (e.g. 'Authorization: Bearer YOUR_SECRET_KEY'). See https://stripe.com/docs/api#authentication for details, or we can help at https://support.stripe.com/.`](missing-api-key-401.md) · GET /v1/customers · HTTP 401
- [A rate-limited request returns HTTP 429 with a Stripe-Rate-Limited-Reason header (global-rate, endpoint-rate, global-concurrency, endpoint-concurrency or resource-specific); a 429 without it is not a rate limit, e.g. lock_timeout.](rate-limited-reason-header.md) · GET /v1/customers · HTTP 429
- [`No such customer: 'cus_apifactsnosuch'`](starting-after-missing-object.md) · GET /v1/customers · HTTP 400 `resource_missing`

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"}}'
```

YAML: [facts/stripe/sandbox-rate-limit-lower.yaml](../../facts/stripe/sandbox-rate-limit-lower.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
