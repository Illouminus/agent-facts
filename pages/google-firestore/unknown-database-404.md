# `the database agentfacts-nosuch-db does not exist for project agent-facts-probes please visit <url> to add a cloud datastore or cloud firestore database.`

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-25 · 13 confirmations from 2 vantages

> A database id the project does not have returns HTTP 404 NOT_FOUND "The database \<id\> does not exist for project \<project\>" with a console link to create one.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:unknown-database` (declarative, [source](../../probes/google-firestore/unknown-database.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}"},"error":{"status":404,"body_excerpt":"the database agentfacts-nosuch-db does not exist for project agent-facts-probes please visit <url> to add a cloud datastore or cloud firestore database."}}'
```

YAML: [facts/google-firestore/unknown-database-404.yaml](../../facts/google-firestore/unknown-database-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
