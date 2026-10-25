# Listing a subcollection under a parent document that does not exist returns HTTP 200 {} rather than 404: the parent's absence is not reported.

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document}/{subcollection} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 63 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:subcollection-of-missing-document` (declarative, [source](../../probes/google-firestore/subcollection-of-missing-document.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}/{subcollection}"},"error":{"status":200}}'
```

YAML: [facts/google-firestore/subcollection-of-missing-document-is-empty.yaml](../../facts/google-firestore/subcollection-of-missing-document-is-empty.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
