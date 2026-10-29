# `method doesn't allow unregistered callers (callers without established identity). please use api key or other form of api consumer identity to call this api.`

**Gemini API · GET /v1beta/models · HTTP 403 `PERMISSION_DENIED`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-29 · 58 confirmations from 2 vantages

> A request with no API key returns HTTP 403 PERMISSION_DENIED ("Method doesn't allow unregistered callers"), not 401.

## What to do

1. Send header x-goog-api-key = the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:models-no-key` (declarative, [source](../../probes/google-gemini/models-no-key.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models"},"error":{"status":403,"body_excerpt":"method doesn'\''t allow unregistered callers (callers without established identity). please use api key or other form of api consumer identity to call this api."}}'
```

YAML: [facts/google-gemini/missing-api-key-403.yaml](../../facts/google-gemini/missing-api-key-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
