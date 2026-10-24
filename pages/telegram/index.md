# Telegram Bot API

Hosts: `api.telegram.org` · 16 facts

## Error meanings

- ✅ verified:server:prod · [`bad request: chat_id is empty`](chat-id-empty-400.md) · GET /{bot_token}/getChat · env prod
- ✅ verified:server:prod · [`bad request: chat not found`](chat-not-found-400.md) · GET /{bot_token}/getChat · env prod
- 🔵 official · [When a group has been migrated to a supergroup, the error's parameters.migrate_to_chat_id holds the supergroup's new identifier.](group-migrated-to-supergroup.md) · POST /{bot_token}/sendMessage · env prod
- ✅ verified:server:prod · [`bad request: invalid file_id`](invalid-file-id-400.md) · GET /{bot_token}/getFile · env prod
- ✅ verified:server:prod · [`not found`](unknown-method-404.md) · GET /{bot_token}/{method} · env prod
- ✅ verified:server:prod · [`bad request: user not found`](user-not-found-400.md) · GET /{bot_token}/{method} · env prod

## Rate limits

- 🔵 official · [Exceeding flood control returns HTTP 429; parameters.retry_after holds the number of seconds left to wait before the request can be repeated.](flood-control-429-retry-after.md) · POST /{bot_token}/sendMessage · env prod
- 🔵 official · [Bots should send no more than one message per second to a chat and at most 20 messages per minute to a group; broadcasts are capped at about 30 messages per second; beyond that the API answers 429.](message-rate-limits.md) · POST /{bot_token}/sendMessage · env prod

## Silent behavior

- ✅ verified:server:prod · [Errors are a JSON object with ok: false, a description and an integer error_code equal to the HTTP status; there is no result field.](error-envelope-ok-false.md) · GET /{bot_token}/{method} · env prod
- 🔵 official · [getUpdates does not work while an outgoing webhook is set up; the webhook has to be removed before updates can be polled.](get-updates-blocked-by-webhook.md) · GET /{bot_token}/getUpdates · env prod
- ✅ verified:server:prod · [getUpdates with limit=0 or limit=1000, outside the documented 1-100, answers HTTP 200 instead of 400.](get-updates-limit-not-validated.md) · GET /{bot_token}/getUpdates · env prod
- ✅ verified:server:prod · [Method names are case-insensitive: /getme and /GETME answer like /getMe.](method-names-case-insensitive.md) · GET /{bot_token}/getMe · env prod
- ✅ verified:server:prod · [For a bot without a webhook, getWebhookInfo returns url as an empty string rather than omitting it, and getUpdates answers ok: true.](no-webhook-url-empty-string.md) · GET /{bot_token}/{method} · env prod
- 🔵 official · [Incoming updates wait on the server until the bot receives them but are not kept longer than 24 hours; an update counts as confirmed once getUpdates is called with a higher offset.](updates-kept-24-hours.md) · GET /{bot_token}/getUpdates · env prod

## Auth quirks

- ✅ verified:server:prod · [`unauthorized`](invalid-token-401.md) · GET /{bot_token}/getMe · env prod
- ✅ verified:server:prod · [`not found`](malformed-token-404.md) · GET /{bot_token}/getMe · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
