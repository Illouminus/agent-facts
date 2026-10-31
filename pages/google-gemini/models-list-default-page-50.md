# GET /v1beta/models without pageSize returns 50 models and a nextPageToken; the rest of the list is only reachable with pageToken.

**Gemini API · GET /v1beta/models · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-31 · 82 confirmations from 2 vantages

## What to do

1. Paginate by nextPageToken via pageToken, ≤ 1000 per page.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:models-default-page` (declarative, [source](../../probes/google-gemini/models-default-page.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models"},"error":{"status":200}}'
```

YAML: [facts/google-gemini/models-list-default-page-50.yaml](../../facts/google-gemini/models-list-default-page-50.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
