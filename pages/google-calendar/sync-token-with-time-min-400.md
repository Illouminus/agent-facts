# `sync token cannot be used with other request restrictions.`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-28 · 45 confirmations from 2 vantages

> A syncToken combined with timeMin returns HTTP 400 "Sync token cannot be used with other request restrictions.".

## What to do

1. Omit query parameter timeMin.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:sync-token-errors` (declarative, [source](../../probes/google-calendar/sync-token-errors.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":400,"body_excerpt":"sync token cannot be used with other request restrictions."}}'
```

YAML: [facts/google-calendar/sync-token-with-time-min-400.yaml](../../facts/google-calendar/sync-token-with-time-min-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
