# `api key not valid. please pass a valid api key.`

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 8 confirmations from 2 vantages

> An API key that does not exist returns HTTP 400 INVALID_ARGUMENT with error.details\[0\].reason API_KEY_INVALID, not 401 or 403.

## What to do

1. Set query parameter key to the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-sheets:probe:invalid-api-key` (declarative, [source](../../probes/google-sheets/invalid-api-key.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"},"error":{"status":400,"body_excerpt":"api key not valid. please pass a valid api key."}}'
```

YAML: [facts/google-sheets/invalid-api-key-400.yaml](../../facts/google-sheets/invalid-api-key-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
