# `bad request`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-29 · 57 confirmations from 2 vantages

> timeMin as a date (2026-10-24) or a time without offset (2026-10-24T00:00:00) returns HTTP 400 with only "Bad Request" (reason badRequest); a timestamp with Z is accepted.

## What to do

1. Encode timeMin as an RFC 3339 timestamp.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:time-min-needs-offset` (declarative, [source](../../probes/google-calendar/time-min-needs-offset.yaml)) · official doc: <https://developers.google.com/workspace/calendar/api/v3/reference/events/list>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":400,"body_excerpt":"bad request"}}'
```

YAML: [facts/google-calendar/time-min-without-offset-bad-request.yaml](../../facts/google-calendar/time-min-without-offset-bad-request.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
