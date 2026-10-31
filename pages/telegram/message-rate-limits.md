# The documented sending limits are about one message per second per chat, 20 messages per minute per group and about 30 messages per second for broadcasts; past them the API answers 429.

**Telegram Bot API · POST /{bot_token}/sendMessage · HTTP 429**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 1000 ms × 2, cap 60000 ms, ≤ 5 attempts, with jitter.

## In your code

When an SDK receives this response:

| SDK | Raises | Check |
| --- | --- | --- |
| Python `python-telegram-bot` (community) | `telegram.error.RetryAfter` | — |
| Node `telegraf` (community) | `TelegramError` | `err.code === 429` |

Read from the SDK source: python-telegram-bot 22.8: telegram/request/\_baserequest.py BaseRequest.\_request_wrapper; telegraf 4.16.3: lib/core/network/client.js callApi, lib/core/network/error.js.

Fix 1:

```python
import random
import time

delay_ms = 1000
for attempt in range(5):
    response = client.send(request)
    if response.status_code != 429:
        break
    time.sleep(random.uniform(0, delay_ms) / 1000)
    delay_ms = min(delay_ms * 2, 60000)
```

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this>

Observations: none from reporters yet.

## Related errors

- [Exceeding flood control returns HTTP 429; parameters.retry_after holds the number of seconds left to wait before the request can be repeated.](flood-control-429-retry-after.md) · POST /{bot_token}/sendMessage · HTTP 429

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.telegram.org/{bot_token}/sendMessage"},"error":{"status":429}}'
```

YAML: [facts/telegram/message-rate-limits.yaml](../../facts/telegram/message-rate-limits.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
