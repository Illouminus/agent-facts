# `document "projects/agent-facts-probes/databases/(default)/documents/agent_facts/nosuch" not found.`

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-28 · 61 confirmations from 2 vantages

> Getting a document that does not exist returns HTTP 404 NOT_FOUND with the full document name in the message (Document "projects/…/documents/\<path\>" not found.).

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:document-not-found` (declarative, [source](../../probes/google-firestore/document-not-found.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}"},"error":{"status":404,"body_excerpt":"document \"projects/agent-facts-probes/databases/(default)/documents/agent_facts/nosuch\" not found."}}'
```

YAML: [facts/google-firestore/document-not-found-404.yaml](../../facts/google-firestore/document-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
