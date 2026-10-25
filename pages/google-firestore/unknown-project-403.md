# `permission denied on resource project agent-facts-nosuch-project-x.`

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 403 `PERMISSION_DENIED`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 13 confirmations from 2 vantages

> A project id that does not exist returns HTTP 403 PERMISSION_DENIED "Permission denied on resource project \<id\>.", the same status as missing IAM rights, not 404.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:unknown-project` (declarative, [source](../../probes/google-firestore/unknown-project.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}"},"error":{"status":403,"body_excerpt":"permission denied on resource project agent-facts-nosuch-project-x."}}'
```

YAML: [facts/google-firestore/unknown-project-403.yaml](../../facts/google-firestore/unknown-project-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
