# A request that Sheets processes for more than 180 seconds returns a timeout error; a 2 MB payload is the recommended maximum.

**Google Sheets API · PUT /v4/spreadsheets/{spreadsheet_id}/values/{range}**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Keep values ≤ 2000000 bytes.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://developers.google.com/workspace/sheets/api/limits>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"PUT","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"}}'
```

YAML: [facts/google-sheets/request-timeout-180s.yaml](../../facts/google-sheets/request-timeout-180s.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
