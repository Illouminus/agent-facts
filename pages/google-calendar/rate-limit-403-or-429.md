# Rate limiting shows up as HTTP 403 with reason rateLimitExceeded or userRateLimitExceeded (domain usageLimits) or as HTTP 429 rateLimitExceeded; a 403 is not always a permission problem.

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 403**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 1000 ms × 2, cap 64000 ms, ≤ 5 attempts, with jitter.

## In your code

When an SDK receives this response:

| SDK | Raises | Check |
| --- | --- | --- |
| Python `google-api-python-client` | `googleapiclient.errors.HttpError` | `e.status_code == 403` |
| Node `googleapis` | `GaxiosError` | `err.status === 403` |

Read from the SDK source: google-api-python-client 2.201.0: googleapiclient/http.py HttpRequest.execute; googleapis 189.0.0 → googleapis-common 9 → gaxios 8.3.2: build/cjs/src/gaxios.js, common.js GaxiosError.

Fix 1:

```python
import random
import time

delay_ms = 1000
for attempt in range(5):
    response = client.send(request)
    if response.status_code != 403:
        break
    time.sleep(random.uniform(0, delay_ms) / 1000)
    delay_ms = min(delay_ms * 2, 64000)
```

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://developers.google.com/workspace/calendar/api/guides/errors>

Observations: none from reporters yet.

## Related errors

- [`Method doesn't allow unregistered callers (callers without established identity). Please use API Key or other form of API consumer identity to call this API.`](missing-api-key-403.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 403
- [`Not Found`](calendar-not-found-404.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 404
- [`Invalid page token value.`](invalid-page-token-400.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400
- [`Invalid value '0'. Values must be within the range: [1, ∞)`](max-results-zero-refused.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400
- [`The requested ordering is not available for the particular query.`](order-by-start-time-needs-single-events.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400
- [`Sync token cannot be used with other request restrictions.`](sync-token-with-time-min-400.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":403}}'
```

YAML: [facts/google-calendar/rate-limit-403-or-429.yaml](../../facts/google-calendar/rate-limit-403-or-429.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
