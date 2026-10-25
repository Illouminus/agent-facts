# pageSize=0 on GET /v1beta/models is not refused: it returns the default page of 50 models with a nextPageToken.

**Gemini API · GET /v1beta/models · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 10 confirmations from 2 vantages

## What to do

1. Paginate by nextPageToken via pageToken, ≤ 1000 per page.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:models-page-size-zero` (declarative, [source](../../probes/google-gemini/models-page-size-zero.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models"},"error":{"status":200}}'
```

YAML: [facts/google-gemini/page-size-zero-means-default.yaml](../../facts/google-gemini/page-size-zero-means-default.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
