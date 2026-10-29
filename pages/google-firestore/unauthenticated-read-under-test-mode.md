# `document "projects/agent-facts-probes/databases/(default)/documents/agent_facts/nosuch" not found.`

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-29 · 77 confirmations from 2 vantages

> While a database runs on test-mode security rules, REST reads with no credentials at all are allowed: a missing document is 404 NOT_FOUND and a list is HTTP 200, rather than 401 or 403.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: test_mode_rules

## Evidence

Probe `af:google-firestore:probe:unauthenticated-test-mode` (declarative, [source](../../probes/google-firestore/unauthenticated-test-mode.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}"},"error":{"status":404,"body_excerpt":"document \"projects/agent-facts-probes/databases/(default)/documents/agent_facts/nosuch\" not found."}}'
```

YAML: [facts/google-firestore/unauthenticated-read-under-test-mode.yaml](../../facts/google-firestore/unauthenticated-read-under-test-mode.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
