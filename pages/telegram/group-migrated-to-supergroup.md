# When a group has been migrated to a supergroup, the error's parameters.migrate_to_chat_id holds the supergroup's new identifier.

**Telegram Bot API · POST /{bot_token}/sendMessage**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://core.telegram.org/bots/api#responseparameters>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.telegram.org/{bot_token}/sendMessage"}}'
```

YAML: [facts/telegram/group-migrated-to-supergroup.yaml](../../facts/telegram/group-migrated-to-supergroup.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
