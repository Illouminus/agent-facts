# `sync token is no longer valid, a full sync is required.`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 410**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-30 · 69 confirmations from 2 vantages

> A syncToken the server does not know, even a made-up string, returns HTTP 410 Gone (reason fullSyncRequired), not 400.

## What to do

1. Omit query parameter syncToken.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:sync-token-errors` (declarative, [source](../../probes/google-calendar/sync-token-errors.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":410,"body_excerpt":"sync token is no longer valid, a full sync is required."}}'
```

YAML: [facts/google-calendar/unknown-sync-token-410.yaml](../../facts/google-calendar/unknown-sync-token-410.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
