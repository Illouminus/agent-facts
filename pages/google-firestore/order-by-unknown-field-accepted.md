# orderBy on a field that no document has is accepted with HTTP 200 instead of being refused.

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-28 · 99 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:order-by-unknown-field` (declarative, [source](../../probes/google-firestore/order-by-unknown-field.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}"},"error":{"status":200}}'
```

YAML: [facts/google-firestore/order-by-unknown-field-accepted.yaml](../../facts/google-firestore/order-by-unknown-field-accepted.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
