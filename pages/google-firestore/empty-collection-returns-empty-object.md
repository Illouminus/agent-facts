# Listing a collection that has no documents returns HTTP 200 with an empty object {}: no documents field (not documents: \[\]) and no nextPageToken.

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-29 · 126 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:empty-collection-empty-object` (declarative, [source](../../probes/google-firestore/empty-collection-empty-object.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}"},"error":{"status":200}}'
```

YAML: [facts/google-firestore/empty-collection-returns-empty-object.yaml](../../facts/google-firestore/empty-collection-returns-empty-object.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
