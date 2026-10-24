# `not found`

**Telegram Bot API · GET /{bot_token}/getMe · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 1 confirmation from 1 vantage

> A /bot\<token\>/ segment whose token lacks the \<digits\>:\<secret\> shape returns HTTP 404 "Not Found", the same answer as an unknown method, not 401.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:invalid-token` (declarative, [source](../../probes/telegram/invalid-token.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getMe"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/telegram/malformed-token-404.yaml](../../facts/telegram/malformed-token-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
