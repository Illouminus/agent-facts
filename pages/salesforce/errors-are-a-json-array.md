# REST errors are a JSON array of objects with errorCode and message (e.g. \[{errorCode: NOT_FOUND, …}\]), not a single error object.

**Salesforce Platform REST API · GET /services/data/{version}/sobjects/{object}/{id} · HTTP 404**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-27 · 128 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:record-not-found` (declarative, [source](../../probes/salesforce/record-not-found.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/sobjects/{object}/{id}"},"error":{"status":404}}'
```

YAML: [facts/salesforce/errors-are-a-json-array.yaml](../../facts/salesforce/errors-are-a-json-array.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
