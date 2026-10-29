# `model is not found: models/gemini-#.#-flash for api version v#beta`

**Gemini API · GET /v1beta/models/{model} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-29 · 92 confirmations from 2 vantages

> The model names gemini-1.5-flash, gemini-1.5-pro and gemini-pro return HTTP 404 NOT_FOUND on GET /v1beta/models/\<name\>.

## What to do

1. Call GET /v1beta/models instead.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:gemini-1-5-retired` (declarative, [source](../../probes/google-gemini/gemini-1-5-retired.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models/{model}"},"error":{"status":404,"body_excerpt":"model is not found: models/gemini-#.#-flash for api version v#beta"}}'
```

YAML: [facts/google-gemini/gemini-1-5-models-retired.yaml](../../facts/google-gemini/gemini-1-5-models-retired.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
