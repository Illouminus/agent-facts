# `page size must be nonnegative.`

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection} · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-26 · 46 confirmations from 2 vantages

> A negative pageSize returns HTTP 400 "Page size must be nonnegative.".

## What to do

1. Omit query parameter pageSize.

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:list-parameter-errors` (declarative, [source](../../probes/google-firestore/list-parameter-errors.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}"},"error":{"status":400,"body_excerpt":"page size must be nonnegative."}}'
```

YAML: [facts/google-firestore/negative-page-size-400.yaml](../../facts/google-firestore/negative-page-size-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
