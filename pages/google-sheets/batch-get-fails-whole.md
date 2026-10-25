# `unable to parse range: agentfactsnosuchsheet!a#`

**Google Sheets API · GET /v4/spreadsheets/{spreadsheet_id}/values:batchGet · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 63 confirmations from 2 vantages

> values:batchGet with an unparsable range fails as a whole with HTTP 400 "Unable to parse range"; without any ranges it returns 200 and no valueRanges field.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-sheets:probe:batch-get-one-bad-range` (declarative, [source](../../probes/google-sheets/batch-get-one-bad-range.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchGet"},"error":{"status":400,"body_excerpt":"unable to parse range: agentfactsnosuchsheet!a#"}}'
```

YAML: [facts/google-sheets/batch-get-fails-whole.yaml](../../facts/google-sheets/batch-get-fails-whole.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
