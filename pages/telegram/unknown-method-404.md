# `not found`

**Telegram Bot API · GET /{bot_token}/{method} · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-27 · 128 confirmations from 2 vantages

> A method name the Bot API does not know returns HTTP 404 {ok: false, error_code: 404, description: "Not Found"}.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:unknown-method` (declarative, [source](../../probes/telegram/unknown-method.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/{method}"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/telegram/unknown-method-404.yaml](../../facts/telegram/unknown-method-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
