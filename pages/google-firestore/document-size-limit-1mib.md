# A document is at most 1 MiB (1,048,576 bytes), an API request at most 10 MiB, and subcollections nest at most 100 levels deep.

**Cloud Firestore (Firebase) REST API · PATCH /v1/projects/{project}/databases/{database}/documents/{collection}/{document}**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Keep fields ≤ 1048576 bytes.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://firebase.google.com/docs/firestore/quotas>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"PATCH","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}"}}'
```

YAML: [facts/google-firestore/document-size-limit-1mib.yaml](../../facts/google-firestore/document-size-limit-1mib.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
