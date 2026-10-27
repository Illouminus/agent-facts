# Errors are a JSON object with ok: false, a description and an integer error_code equal to the HTTP status (documented as subject to change); there is no result field.

**Telegram Bot API · GET /{bot_token}/{method} · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-27 · 80 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:telegram:probe:error-envelope` (declarative, [source](../../probes/telegram/error-envelope.yaml)) · official doc: <https://core.telegram.org/bots/api#making-requests>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.telegram.org/{bot_token}/{method}"},"error":{"status":400}}'
```

YAML: [facts/telegram/error-envelope-ok-false.yaml](../../facts/telegram/error-envelope-ok-false.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
