# events.list returns at most 250 events per page by default and never more than 2500; further pages need pageToken.

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Paginate by nextPageToken via pageToken, ≤ 2500 per page.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://developers.google.com/workspace/calendar/api/v3/reference/events/list>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"}}'
```

YAML: [facts/google-calendar/events-page-default-250.yaml](../../facts/google-calendar/events-page-default-250.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
