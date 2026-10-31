# `Too many requests hit the API too quickly. We recommend an exponential backoff of your requests.`

**Stripe · GET /v1/customers/{id} · HTTP 429 `rate_limit`**

Status: 🟡 reported · first seen 2026-10-26 · last confirmed 2026-10-28 · not yet reproduced by a probe

> Bursts of customer retrievals return HTTP 429 rate_limit before the documented global rate is reached.

## What to do

1. Retry with exponential backoff from 500 ms × 2, cap 8000 ms, ≤ 5 attempts, with jitter.

## In your code

When an SDK receives this response:

| SDK | Raises | Check |
| --- | --- | --- |
| Python `stripe` | `stripe.RateLimitError` | `e.http_status == 429` |
| Node `stripe` | `Stripe.errors.StripeRateLimitError` | `err.statusCode === 429` |

Read from the SDK source: stripe 16.1.0: stripe/\_api_requestor.py specific_v1_api_error, stripe/\_error.py; stripe 23.1.0: cjs/Error.js generateV1Error, cjs/RequestSender.js.

Fix 1:

```python
import random
import time

delay_ms = 500
for attempt in range(5):
    response = client.send(request)
    if response.status_code != 429:
        break
    time.sleep(random.uniform(0, delay_ms) / 1000)
    delay_ms = min(delay_ms * 2, 8000)
```

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

No probe or official document yet.

Observations: 5 distinct reporter networks.

## Machine access

Match signature (what `check()` matches): `too many requests hit the api too quickly. we recommend an exponential backoff of your requests.`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers/{id}"},"error":{"status":429,"body_excerpt":"too many requests hit the api too quickly. we recommend an exponential backoff of your requests."}}'
```

YAML: [facts/stripe/customer-retrieve-rate-limit.yaml](../../facts/stripe/customer-retrieve-rate-limit.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
