# `bad request: chat_id is empty`

**Telegram Bot API · GET /{bot_token}/getChat · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 19 confirmations from 2 vantages

> getChat called without chat_id returns HTTP 400 "Bad Request: chat_id is empty".

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:get-chat-id-empty` (declarative, [source](../../probes/telegram/get-chat-id-empty.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getChat"},"error":{"status":400,"body_excerpt":"bad request: chat_id is empty"}}'
```

YAML: [facts/telegram/chat-id-empty-400.yaml](../../facts/telegram/chat-id-empty-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
