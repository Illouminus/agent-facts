# gemini-2.0-flash, whose earliest shutdown date on the deprecations page is June 1, 2026, still answers GET /v1beta/models/gemini-2.0-flash with HTTP 200 and version 2.0.

**Gemini API · GET /v1beta/models/{model} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 15 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:gemini-2-0-flash-served` (declarative, [source](../../probes/google-gemini/gemini-2-0-flash-served.yaml)) · official doc: <https://ai.google.dev/gemini-api/docs/deprecations>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models/{model}"},"error":{"status":200}}'
```

YAML: [facts/google-gemini/gemini-2-0-flash-served-past-shutdown-date.yaml](../../facts/google-gemini/gemini-2-0-flash-served-past-shutdown-date.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
