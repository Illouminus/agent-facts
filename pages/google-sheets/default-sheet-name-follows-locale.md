# `unable to parse range: sheet#!a#`

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 7 confirmations from 2 vantages

> The first sheet is not always Sheet1: on this French-locale spreadsheet it is Feuille 1, and Sheet1!A1 returns HTTP 400 "Unable to parse range: Sheet1!A1"; a range without a sheet name reads the first sheet.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-sheets:probe:default-sheet-name-localized` (declarative, [source](../../probes/google-sheets/default-sheet-name-localized.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"},"error":{"status":400,"body_excerpt":"unable to parse range: sheet#!a#"}}'
```

YAML: [facts/google-sheets/default-sheet-name-follows-locale.yaml](../../facts/google-sheets/default-sheet-name-follows-locale.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
