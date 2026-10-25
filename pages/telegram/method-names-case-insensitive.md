# Method names are case-insensitive: /getme and /GETME answer like /getMe.

**Telegram Bot API · GET /{bot_token}/getMe · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 33 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:method-names-case-insensitive` (declarative, [source](../../probes/telegram/method-names-case-insensitive.yaml)) · official doc: <https://core.telegram.org/bots/api#making-requests>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/getMe"},"error":{"status":200}}'
```

YAML: [facts/telegram/method-names-case-insensitive.yaml](../../facts/telegram/method-names-case-insensitive.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
