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

## Related errors

- [`Not Found`](calendar-not-found-404.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 404
- [`Invalid page token value.`](invalid-page-token-400.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400
- [`Invalid value '0'. Values must be within the range: [1, ∞)`](max-results-zero-refused.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400
- [`Method doesn't allow unregistered callers (callers without established identity). Please use API Key or other form of API consumer identity to call this API.`](missing-api-key-403.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 403
- [`The requested ordering is not available for the particular query.`](order-by-start-time-needs-single-events.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400
- [Rate limiting shows up as HTTP 403 with reason rateLimitExceeded or userRateLimitExceeded (domain usageLimits) or as HTTP 429 rateLimitExceeded; a 403 is not always a permission problem.](rate-limit-403-or-429.md) · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 403

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"}}'
```

YAML: [facts/google-calendar/events-page-default-250.yaml](../../facts/google-calendar/events-page-default-250.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
