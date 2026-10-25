# The documented sending limits are about one message per second per chat, 20 messages per minute per group and about 30 messages per second for broadcasts; past them the API answers 429.

**Telegram Bot API · POST /{bot_token}/sendMessage · HTTP 429**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 1000 ms × 2, cap 60000 ms, ≤ 5 attempts, with jitter.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.telegram.org/{bot_token}/sendMessage"},"error":{"status":429}}'
```

YAML: [facts/telegram/message-rate-limits.yaml](../../facts/telegram/message-rate-limits.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
