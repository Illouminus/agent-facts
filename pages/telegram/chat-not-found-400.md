# `bad request: chat not found`

**Telegram Bot API · GET /{bot_token}/getChat · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-31 · 196 confirmations from 2 vantages

> getChat for a chat the bot has never seen (chat_id=1) returns HTTP 400 {ok: false, error_code: 400, description: "Bad Request: chat not found"}.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:get-chat-not-found` (declarative, [source](../../probes/telegram/get-chat-not-found.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getChat"},"error":{"status":400,"body_excerpt":"bad request: chat not found"}}'
```

YAML: [facts/telegram/chat-not-found-400.yaml](../../facts/telegram/chat-not-found-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
