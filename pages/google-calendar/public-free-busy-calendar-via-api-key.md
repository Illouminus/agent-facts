# events.list with only an API key works on a calendar shared publicly as free/busy: HTTP 200 with accessRole freeBusyReader, items and a nextSyncToken.

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 10 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:events-free-busy-reader` (declarative, [source](../../probes/google-calendar/events-free-busy-reader.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":200}}'
```

YAML: [facts/google-calendar/public-free-busy-calendar-via-api-key.yaml](../../facts/google-calendar/public-free-busy-calendar-via-api-key.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
