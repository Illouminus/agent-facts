# timeMin is an exclusive lower bound on an event's end time, not its start time; timeMax is an exclusive upper bound on the start time.

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://developers.google.com/workspace/calendar/api/v3/reference/events/list>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"}}'
```

YAML: [facts/google-calendar/time-min-filters-on-end-time.yaml](../../facts/google-calendar/time-min-filters-on-end-time.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
