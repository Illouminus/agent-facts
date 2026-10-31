# `Method doesn't allow unregistered callers (callers without established identity). Please use API Key or other form of API consumer identity to call this API.`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 403**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-31 · 81 confirmations from 2 vantages

> events.list on a public calendar with no API key or token returns HTTP 403 ("Method doesn't allow unregistered callers").

## What to do

1. Set query parameter key to the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-calendar:probe:no-api-key` (declarative, [source](../../probes/google-calendar/no-api-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `method doesn't allow unregistered callers (callers without established identity). please use api key or other form of api consumer identity to call this api.`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":403,"body_excerpt":"method doesn'\''t allow unregistered callers (callers without established identity). please use api key or other form of api consumer identity to call this api."}}'
```

YAML: [facts/google-calendar/missing-api-key-403.yaml](../../facts/google-calendar/missing-api-key-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
