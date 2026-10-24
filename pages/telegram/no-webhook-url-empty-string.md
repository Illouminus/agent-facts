# For a bot without a webhook, getWebhookInfo returns url as an empty string rather than omitting it, and getUpdates answers ok: true.

**Telegram Bot API · GET /{bot_token}/{method} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 2 confirmations from 1 vantage

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: no_webhook

## Evidence

Probe `af:telegram:probe:no-webhook-state` (declarative, [source](../../probes/telegram/no-webhook-state.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/{method}"},"error":{"status":200}}'
```

YAML: [facts/telegram/no-webhook-url-empty-string.yaml](../../facts/telegram/no-webhook-url-empty-string.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
