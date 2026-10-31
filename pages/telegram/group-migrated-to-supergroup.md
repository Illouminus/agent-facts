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

## Related errors

- [Exceeding flood control returns HTTP 429; parameters.retry_after holds the number of seconds left to wait before the request can be repeated.](flood-control-429-retry-after.md) · POST /{bot_token}/sendMessage · HTTP 429
- [The documented sending limits are about one message per second per chat, 20 messages per minute per group and about 30 messages per second for broadcasts; past them the API answers 429.](message-rate-limits.md) · POST /{bot_token}/sendMessage · HTTP 429

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.telegram.org/{bot_token}/sendMessage"}}'
```

YAML: [facts/telegram/group-migrated-to-supergroup.yaml](../../facts/telegram/group-migrated-to-supergroup.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
