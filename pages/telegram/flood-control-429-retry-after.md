# Exceeding flood control returns HTTP 429; parameters.retry_after holds the number of seconds left to wait before the request can be repeated.

**Telegram Bot API · POST /{bot_token}/sendMessage · HTTP 429**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 1000 ms × 2, cap 60000 ms, ≤ 5 attempts, with jitter.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://core.telegram.org/bots/api#responseparameters>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.telegram.org/{bot_token}/sendMessage"},"error":{"status":429}}'
```

YAML: [facts/telegram/flood-control-429-retry-after.yaml](../../facts/telegram/flood-control-429-retry-after.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
