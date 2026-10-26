# `not found`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-26 · 22 confirmations from 2 vantages

> events.list on a calendar id that does not exist returns HTTP 404 "Not Found" with error.errors\[0\].reason notFound and no error.status.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:calendar-not-found` (declarative, [source](../../probes/google-calendar/calendar-not-found.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/google-calendar/calendar-not-found-404.yaml](../../facts/google-calendar/calendar-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
