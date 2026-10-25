# `unable to parse range: agentfactsnosuchsheet!a#`

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 7 confirmations from 2 vantages

> A range naming a sheet that does not exist returns HTTP 400 INVALID_ARGUMENT "Unable to parse range: \<range\>".

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-sheets:probe:unknown-sheet-range` (declarative, [source](../../probes/google-sheets/unknown-sheet-range.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"},"error":{"status":400,"body_excerpt":"unable to parse range: agentfactsnosuchsheet!a#"}}'
```

YAML: [facts/google-sheets/unknown-sheet-unable-to-parse.yaml](../../facts/google-sheets/unknown-sheet-unable-to-parse.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
