# Server client libraries bypass all Firestore security rules and authenticate with Application Default Credentials, so their access is decided by IAM, not by the rules.

**Cloud Firestore (Firebase) REST API · POST /v1/projects/{project}/databases/{database}/documents:runQuery**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://firebase.google.com/docs/firestore/security/get-started>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents:runQuery"}}'
```

YAML: [facts/google-firestore/server-access-bypasses-security-rules.yaml](../../facts/google-firestore/server-access-bypasses-security-rules.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
