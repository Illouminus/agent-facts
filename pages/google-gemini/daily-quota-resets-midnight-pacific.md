# Requests-per-day quotas reset at midnight Pacific time, not at midnight UTC.

**Gemini API · POST /v1beta/models/{model_and_method}**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://ai.google.dev/gemini-api/docs/rate-limits>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://generativelanguage.googleapis.com/v1beta/models/{model_and_method}"}}'
```

YAML: [facts/google-gemini/daily-quota-resets-midnight-pacific.yaml](../../facts/google-gemini/daily-quota-resets-midnight-pacific.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
