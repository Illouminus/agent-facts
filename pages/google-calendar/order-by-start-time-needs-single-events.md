# `the requested ordering is not available for the particular query.`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-26 · 21 confirmations from 2 vantages

> orderBy=startTime without singleEvents=true returns HTTP 400 "The requested ordering is not available for the particular query."; with singleEvents=true it succeeds.

## What to do

1. Set query parameter singleEvents to true.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:order-by-start-time` (declarative, [source](../../probes/google-calendar/order-by-start-time.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":400,"body_excerpt":"the requested ordering is not available for the particular query."}}'
```

YAML: [facts/google-calendar/order-by-start-time-needs-single-events.yaml](../../facts/google-calendar/order-by-start-time-needs-single-events.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
