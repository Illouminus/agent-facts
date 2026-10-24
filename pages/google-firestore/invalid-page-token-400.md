# `invalid page token`

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection} · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 2 confirmations from 1 vantage

> A pageToken the API did not issue returns HTTP 400 "invalid page token" (lowercase, no period).

## What to do

1. Paginate by nextPageToken via pageToken, ≤ 300 per page.

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:list-parameter-errors` (declarative, [source](../../probes/google-firestore/list-parameter-errors.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}"},"error":{"status":400,"body_excerpt":"invalid page token"}}'
```

YAML: [facts/google-firestore/invalid-page-token-400.yaml](../../facts/google-firestore/invalid-page-token-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
