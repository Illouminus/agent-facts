# getUpdates does not work while an outgoing webhook is set up; the webhook has to be removed before updates can be polled.

**Telegram Bot API · GET /{bot_token}/getUpdates**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: webhook_set · also seen: [any](updates-kept-24-hours.md) (official 2026-10-24)

## Evidence

official doc: <https://core.telegram.org/bots/api#getupdates>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getUpdates"}}'
```

YAML: [facts/telegram/get-updates-blocked-by-webhook.yaml](../../facts/telegram/get-updates-blocked-by-webhook.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
