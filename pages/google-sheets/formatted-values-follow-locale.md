# By default values.get returns every cell as a string formatted in the spreadsheet's locale: on a fr_FR file 3.14159 comes back as "3,14159", a date as "24/10/2026" and a boolean as "TRUE".

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-31 · 50 confirmations from 2 vantages

## What to do

1. Set query parameter valueRenderOption to UNFORMATTED_VALUE.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-sheets:probe:fixture-formatted-values` (declarative, [source](../../probes/google-sheets/fixture-formatted-values.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"},"error":{"status":200}}'
```

YAML: [facts/google-sheets/formatted-values-follow-locale.yaml](../../facts/google-sheets/formatted-values-follow-locale.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
