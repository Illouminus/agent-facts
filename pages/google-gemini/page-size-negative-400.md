# `* listmodelsrequest.page_size: page_size must be positive`

**Gemini API · GET /v1beta/models · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-30 · 70 confirmations from 2 vantages

> A negative pageSize returns HTTP 400 INVALID_ARGUMENT "\* ListModelsRequest.page_size: page_size must be positive".

## What to do

1. Omit query parameter pageSize.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:models-page-size-negative` (declarative, [source](../../probes/google-gemini/models-page-size-negative.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models"},"error":{"status":400,"body_excerpt":"* listmodelsrequest.page_size: page_size must be positive"}}'
```

YAML: [facts/google-gemini/page-size-negative-400.yaml](../../facts/google-gemini/page-size-negative-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
