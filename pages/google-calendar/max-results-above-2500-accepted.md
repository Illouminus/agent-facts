# maxResults=5000, above the documented page maximum of 2500, is accepted with HTTP 200 rather than refused (the error message for 0 even gives the range as \[1, ∞)).

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-30 · 69 confirmations from 2 vantages

## What to do

1. Paginate by nextPageToken via pageToken, ≤ 2500 per page.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:max-results-bounds` (declarative, [source](../../probes/google-calendar/max-results-bounds.yaml)) · official doc: <https://developers.google.com/workspace/calendar/api/v3/reference/events/list>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":200}}'
```

YAML: [facts/google-calendar/max-results-above-2500-accepted.yaml](../../facts/google-calendar/max-results-above-2500-accepted.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
