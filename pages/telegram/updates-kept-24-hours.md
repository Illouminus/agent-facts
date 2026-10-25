# Incoming updates wait on the server until the bot receives them but are not kept longer than 24 hours; an update counts as confirmed once getUpdates is called with a higher offset.

**Telegram Bot API · GET /{bot_token}/getUpdates**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any · also seen: [webhook_set](get-updates-blocked-by-webhook.md) (official 2026-10-24)

## Evidence

official doc: <https://core.telegram.org/bots/api#getting-updates>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getUpdates"}}'
```

YAML: [facts/telegram/updates-kept-24-hours.yaml](../../facts/telegram/updates-kept-24-hours.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
