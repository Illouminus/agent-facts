# `invalid page_token.`

**Gemini API · GET /v1beta/models · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-31 · 82 confirmations from 2 vantages

> A pageToken that the API did not issue returns HTTP 400 INVALID_ARGUMENT "Invalid page_token.".

## What to do

1. Paginate by nextPageToken via pageToken, ≤ 1000 per page.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:models-invalid-page-token` (declarative, [source](../../probes/google-gemini/models-invalid-page-token.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models"},"error":{"status":400,"body_excerpt":"invalid page_token."}}'
```

YAML: [facts/google-gemini/invalid-page-token-400.yaml](../../facts/google-gemini/invalid-page-token-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
