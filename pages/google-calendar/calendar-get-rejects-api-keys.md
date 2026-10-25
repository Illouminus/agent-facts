# `api keys are not supported by this api. expected oauth# access token or other authentication credentials that assert a principal. see <url>`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id} · HTTP 401 `UNAUTHENTICATED`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 62 confirmations from 2 vantages

> The API key that lists a public calendar's events gets HTTP 401 UNAUTHENTICATED ("API keys are not supported by this API") on calendars.get and users/me/calendarList.

## What to do

1. Request OAuth scope https://www.googleapis.com/auth/calendar.readonly.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:calendar-get-needs-oauth` (declarative, [source](../../probes/google-calendar/calendar-get-needs-oauth.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}"},"error":{"status":401,"body_excerpt":"api keys are not supported by this api. expected oauth# access token or other authentication credentials that assert a principal. see <url>"}}'
```

YAML: [facts/google-calendar/calendar-get-rejects-api-keys.yaml](../../facts/google-calendar/calendar-get-rejects-api-keys.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
