# `model is not found: models/gemini-flash-latest for api version v#`

**Gemini API · GET /v1/models/{model} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-28 · 72 confirmations from 2 vantages

> The alias gemini-flash-latest and preview models such as gemini-3-flash-preview answer on v1beta but return HTTP 404 NOT_FOUND on v1.

## What to do

1. Call GET /v1beta/models/{model} instead.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:latest-alias-v1beta-only` (declarative, [source](../../probes/google-gemini/latest-alias-v1beta-only.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1/models/{model}"},"error":{"status":404,"body_excerpt":"model is not found: models/gemini-flash-latest for api version v#"}}'
```

YAML: [facts/google-gemini/latest-aliases-v1beta-only.yaml](../../facts/google-gemini/latest-aliases-v1beta-only.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
