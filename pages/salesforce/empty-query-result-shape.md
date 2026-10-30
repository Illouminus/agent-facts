# A SOQL query that matches nothing returns HTTP 200 with totalSize 0, done true and an empty records array, and no nextRecordsUrl.

**Salesforce Platform REST API · GET /services/data/{version}/query · HTTP 200**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-30 · 93 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:soql-empty-result` (declarative, [source](../../probes/salesforce/soql-empty-result.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/query"},"error":{"status":200}}'
```

YAML: [facts/salesforce/empty-query-result-shape.yaml](../../facts/salesforce/empty-query-result-shape.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
