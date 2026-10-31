# ``invalid property path "a b". unquoted property paths must match regex ([a-za-z_][a-za-z_#-#]*), and quoted property paths must match regex (`(?:[^`\\]|(?:\\.))+`)``

**Cloud Firestore (Firebase) REST API · GET /v1/projects/{project}/databases/{database}/documents/{collection} · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-31 · 179 confirmations from 2 vantages

> A mask.fieldPaths entry with a space or other character outside \[a-zA-Z\_\]\[a-zA-Z_0-9\]\* returns HTTP 400 "Invalid property path" unless the path is quoted in backticks.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: service_account

## Evidence

Probe `af:google-firestore:probe:list-parameter-errors` (declarative, [source](../../probes/google-firestore/list-parameter-errors.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}"},"error":{"status":400,"body_excerpt":"invalid property path \"a b\". unquoted property paths must match regex ([a-za-z_][a-za-z_#-#]*), and quoted property paths must match regex (`(?:[^`\\\\]|(?:\\\\.))+`)"}}'
```

YAML: [facts/google-firestore/invalid-field-path-400.yaml](../../facts/google-firestore/invalid-field-path-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
