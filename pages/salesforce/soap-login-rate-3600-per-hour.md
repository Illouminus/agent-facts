# login() is limited to 3,600 calls per user per hour; past it the call fails with "Login Rate Exceeded" and the user is blocked from logging in for an hour.

**Salesforce Platform REST API · POST /services/Soap/u/{version}**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 60000 ms × 2, cap 3600000 ms, ≤ 3 attempts, with jitter.

## In your code

Fix 1:

```python
import random
import time

delay_ms = 60000
for attempt in range(3):
    response = client.send(request)
    if response.is_success:
        break
    time.sleep(random.uniform(0, delay_ms) / 1000)
    delay_ms = min(delay_ms * 2, 3600000)
```

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

official doc: <https://developer.salesforce.com/docs/platform/api/guide/sforce-api-calls-login.html>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://login.salesforce.com/services/Soap/u/{version}"}}'
```

YAML: [facts/salesforce/soap-login-rate-3600-per-hour.yaml](../../facts/salesforce/soap-login-rate-3600-per-hour.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
