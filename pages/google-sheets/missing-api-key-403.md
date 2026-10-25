# `method doesn't allow unregistered callers (callers without established identity). please use api key or other form of api consumer identity to call this api.`

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · HTTP 403 `PERMISSION_DENIED`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 7 confirmations from 2 vantages

> Reading even a public spreadsheet with no API key or token returns HTTP 403 PERMISSION_DENIED ("Method doesn't allow unregistered callers").

## What to do

1. Set query parameter key to the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-sheets:probe:no-api-key` (declarative, [source](../../probes/google-sheets/no-api-key.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"},"error":{"status":403,"body_excerpt":"method doesn'\''t allow unregistered callers (callers without established identity). please use api key or other form of api consumer identity to call this api."}}'
```

YAML: [facts/google-sheets/missing-api-key-403.yaml](../../facts/google-sheets/missing-api-key-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
