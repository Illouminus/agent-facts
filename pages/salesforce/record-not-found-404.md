# `the requested resource does not exist`

**Salesforce Platform REST API · GET /services/data/{version}/sobjects/{object}/{id} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-26 · 80 confirmations from 2 vantages

> Retrieving a record id that does not exist returns HTTP 404 NOT_FOUND "The requested resource does not exist".

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
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/sobjects/{object}/{id}"},"error":{"status":404,"body_excerpt":"the requested resource does not exist"}}'
```

YAML: [facts/salesforce/record-not-found-404.yaml](../../facts/salesforce/record-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
