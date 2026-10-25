# `bad request: invalid file_id`

**Telegram Bot API · GET /{bot_token}/getFile · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 63 confirmations from 2 vantages

> getFile with a file_id that is not one Telegram issued returns HTTP 400 "Bad Request: invalid file_id".

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:get-file-invalid` (declarative, [source](../../probes/telegram/get-file-invalid.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getFile"},"error":{"status":400,"body_excerpt":"bad request: invalid file_id"}}'
```

YAML: [facts/telegram/invalid-file-id-400.yaml](../../facts/telegram/invalid-file-id-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
