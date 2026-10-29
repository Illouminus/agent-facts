# getUpdates with limit=0 or limit=1000, outside the documented 1-100, answers HTTP 200 instead of 400.

**Telegram Bot API · GET /{bot_token}/getUpdates · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-29 · 219 confirmations from 2 vantages

## What to do

1. Set query parameter limit to 100.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:get-updates-limit-out-of-range` (declarative, [source](../../probes/telegram/get-updates-limit-out-of-range.yaml)) · official doc: <https://core.telegram.org/bots/api#getupdates>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getUpdates"},"error":{"status":200}}'
```

YAML: [facts/telegram/get-updates-limit-not-validated.yaml](../../facts/telegram/get-updates-limit-not-validated.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
