# With valueRenderOption=UNFORMATTED_VALUE numbers and booleans are JSON numbers and booleans, and a date is its serial number: 2026-10-24 comes back as 46319.

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-31 · 50 confirmations from 2 vantages

## What to do

1. Set query parameter dateTimeRenderOption to FORMATTED_STRING.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-sheets:probe:fixture-unformatted-values` (declarative, [source](../../probes/google-sheets/fixture-unformatted-values.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"},"error":{"status":200}}'
```

YAML: [facts/google-sheets/unformatted-dates-are-serial-numbers.yaml](../../facts/google-sheets/unformatted-dates-are-serial-numbers.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
