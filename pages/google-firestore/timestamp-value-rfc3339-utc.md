# A timestamp field comes back as timestampValue, an RFC 3339 string in UTC with a Z suffix ("2026-10-24T00:00:00Z").

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 1 confirmation from 1 vantage

## What to do

1. Encode timestampValue as an RFC 3339 timestamp.

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:typed-document` (declarative, [source](../../probes/google-firestore/typed-document.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{document}"},"error":{"status":200}}'
```

YAML: [facts/google-firestore/timestamp-value-rfc3339-utc.yaml](../../facts/google-firestore/timestamp-value-rfc3339-utc.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
