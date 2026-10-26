# `requested entity was not found.`

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-26 · 15 confirmations from 2 vantages

> A spreadsheet id that does not exist returns HTTP 404 NOT_FOUND "Requested entity was not found.".

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-sheets:probe:spreadsheet-not-found` (declarative, [source](../../probes/google-sheets/spreadsheet-not-found.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"},"error":{"status":404,"body_excerpt":"requested entity was not found."}}'
```

YAML: [facts/google-sheets/spreadsheet-not-found-404.yaml](../../facts/google-sheets/spreadsheet-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
