# `unauthorized`

**Telegram Bot API · GET /{bot_token}/getMe · HTTP 401**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-28 · 348 confirmations from 2 vantages

> A token-shaped bot token (\<digits\>:\<secret\>) that is not valid returns HTTP 401 {ok: false, description: "Unauthorized"}.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:invalid-token` (declarative, [source](../../probes/telegram/invalid-token.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getMe"},"error":{"status":401,"body_excerpt":"unauthorized"}}'
```

YAML: [facts/telegram/invalid-token-401.yaml](../../facts/telegram/invalid-token-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
