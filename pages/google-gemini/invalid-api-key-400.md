# `api key not valid. please pass a valid api key.`

**Gemini API · GET /v1beta/models · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 2 confirmations from 1 vantage

> An API key that does not exist returns HTTP 400 INVALID_ARGUMENT, not 401 or 403; error.details\[0\].reason is API_KEY_INVALID.

## What to do

1. Send header x-goog-api-key = the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:models-invalid-key` (declarative, [source](../../probes/google-gemini/models-invalid-key.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models"},"error":{"status":400,"body_excerpt":"api key not valid. please pass a valid api key."}}'
```

YAML: [facts/google-gemini/invalid-api-key-400.yaml](../../facts/google-gemini/invalid-api-key-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
