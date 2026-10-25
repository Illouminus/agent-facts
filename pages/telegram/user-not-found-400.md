# `bad request: user not found`

**Telegram Bot API · GET /{bot_token}/{method} · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 63 confirmations from 2 vantages

> getUserProfilePhotos for a user_id the bot cannot see returns HTTP 400 "Bad Request: user not found".

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:user-photos-unknown-user` (declarative, [source](../../probes/telegram/user-photos-unknown-user.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/{method}"},"error":{"status":400,"body_excerpt":"bad request: user not found"}}'
```

YAML: [facts/telegram/user-not-found-400.yaml](../../facts/telegram/user-not-found-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
