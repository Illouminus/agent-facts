# `invalid page token value.`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-26 · 22 confirmations from 2 vantages

> A pageToken the API did not issue returns HTTP 400 "Invalid page token value.".

## What to do

1. Paginate by nextPageToken via pageToken, ≤ 2500 per page.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:invalid-page-token` (declarative, [source](../../probes/google-calendar/invalid-page-token.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":400,"body_excerpt":"invalid page token value."}}'
```

YAML: [facts/google-calendar/invalid-page-token-400.yaml](../../facts/google-calendar/invalid-page-token-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
