# In REST documents an integer field comes back as a JSON string (integerValue: "42", int64 format), while a double is a JSON number (doubleValue: 3.5).

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-29 · 75 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:typed-document` (declarative, [source](../../probes/google-firestore/typed-document.yaml)) · official doc: <https://firebase.google.com/docs/firestore/reference/rest/v1/Value>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}"},"error":{"status":200}}'
```

YAML: [facts/google-firestore/integer-value-is-a-string.yaml](../../facts/google-firestore/integer-value-is-a-string.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
