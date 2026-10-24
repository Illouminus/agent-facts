# `invalid value at 'value_render_option' (type.googleapis.com/google.apps.sheets.v#.valuerenderoption), "pretty"`

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 3 confirmations from 1 vantage

> An unknown valueRenderOption returns HTTP 400 INVALID_ARGUMENT naming the field in snake_case (value_render_option) and the rejected value.

## What to do

1. Set query parameter valueRenderOption to FORMATTED_VALUE.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-sheets:probe:invalid-value-render-option` (declarative, [source](../../probes/google-sheets/invalid-value-render-option.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"},"error":{"status":400,"body_excerpt":"invalid value at '\''value_render_option'\'' (type.googleapis.com/google.apps.sheets.v#.valuerenderoption), \"pretty\""}}'
```

YAML: [facts/google-sheets/invalid-value-render-option-400.yaml](../../facts/google-sheets/invalid-value-render-option-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
