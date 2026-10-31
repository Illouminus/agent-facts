# `invalid value '#'. values must be within the range: [#, ∞)`

**Google Calendar API · GET /calendar/v3/calendars/{calendar_id}/events · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-31 · 81 confirmations from 2 vantages

> maxResults=0 returns HTTP 400 "Invalid value '0'. Values must be within the range: \[1, ∞)" (reason invalidParameter).

## What to do

1. Set query parameter maxResults to 250.

## Dimensions

env: prod · plan: any · region: any · account_state: api_key

## Evidence

Probe `af:google-calendar:probe:max-results-bounds` (declarative, [source](../../probes/google-calendar/max-results-bounds.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"},"error":{"status":400,"body_excerpt":"invalid value '\''#'\''. values must be within the range: [#, ∞)"}}'
```

YAML: [facts/google-calendar/max-results-zero-refused.yaml](../../facts/google-calendar/max-results-zero-refused.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
