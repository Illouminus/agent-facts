# The free quota is 50,000 document reads and 20,000 writes and 20,000 deletes per day, reset around midnight Pacific time.

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document}**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://firebase.google.com/docs/firestore/quotas>

Observations: none from reporters yet.

## Related errors

- [`Document "projects/agent-facts-probes/databases/(default)/documents/agent_facts/nosuch" not found.`](document-not-found-404.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 404 `NOT_FOUND`
- [`Document "projects/agent-facts-probes/databases/(default)/documents/agent_facts/nosuch" not found.`](unauthenticated-read-under-test-mode.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 404 `NOT_FOUND`
- [`The database agentfacts-nosuch-db does not exist for project agent-facts-probes Please visit https://console.cloud.google.com/datastore/setup?project=agent-facts-probes to add a Cloud Datastore or Cloud Firestore database.`](unknown-database-404.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 404 `NOT_FOUND`
- [`Permission denied on resource project agent-facts-nosuch-project-x.`](unknown-project-403.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 403 `PERMISSION_DENIED`

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}"}}'
```

YAML: [facts/google-firestore/free-quota-resets-midnight-pacific.yaml](../../facts/google-firestore/free-quota-resets-midnight-pacific.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
