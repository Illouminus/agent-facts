# Google Calendar API

Hosts: `www.googleapis.com` · 14 facts

## Error meanings

- ✅ verified:server:prod · [`not found`](calendar-not-found-404.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod
- ✅ verified:server:prod · [`invalid value '#'. values must be within the range: [#, ∞)`](max-results-zero-refused.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod
- ✅ verified:server:prod · [`the requested ordering is not available for the particular query.`](order-by-start-time-needs-single-events.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod
- ✅ verified:server:prod · [`sync token cannot be used with other request restrictions.`](sync-token-with-time-min-400.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod
- ✅ verified:server:prod · [`bad request`](time-min-without-offset-bad-request.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod
- ✅ verified:server:prod · [`sync token is no longer valid, a full sync is required.`](unknown-sync-token-410.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod

## Rate limits

- 🔵 official · [Rate limiting shows up as HTTP 403 with reason rateLimitExceeded or userRateLimitExceeded (domain usageLimits) or as HTTP 429 rateLimitExceeded; a 403 is not always a permission problem.](rate-limit-403-or-429.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod

## Silent behavior

- 🔵 official · [timeMin is an exclusive lower bound on an event's end time, not its start time; timeMax is an exclusive upper bound on the start time.](time-min-filters-on-end-time.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod

## Auth quirks

- ✅ verified:server:prod · [`api keys are not supported by this api. expected oauth# access token or other authentication credentials that assert a principal. see <url>`](calendar-get-rejects-api-keys.md) · GET /calendar/v3/calendars/{calendar_id} · env prod
- ✅ verified:server:prod · [`method doesn't allow unregistered callers (callers without established identity). please use api key or other form of api consumer identity to call this api.`](missing-api-key-403.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod
- ✅ verified:server:prod · [events.list with only an API key works on a calendar shared publicly as free/busy: HTTP 200 with accessRole freeBusyReader, items and a nextSyncToken.](public-free-busy-calendar-via-api-key.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod

## Pagination

- 🔵 official · [events.list returns at most 250 events per page by default and never more than 2500; further pages need pageToken.](events-page-default-250.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod
- ✅ verified:server:prod · [`invalid page token value.`](invalid-page-token-400.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod
- ✅ verified:server:prod · [maxResults=5000, above the documented page maximum of 2500, is accepted with HTTP 200 rather than refused (the error message for 0 even gives the range as \[1, ∞)).](max-results-above-2500-accepted.md) · GET /calendar/v3/calendars/{calendar_id}/events · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
