# `the requested resource no longer exists.`

**Salesforce Platform REST API · GET /services/data/{version}/limits · HTTP 410**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-25 · 20 confirmations from 2 vantages

> A retired REST API version (v30.0) returns HTTP 410 "The requested resource no longer exists.", while a version that does not exist yet (v99.0) returns 404.

## What to do

1. Call GET /services/data instead.

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:api-version-retired-or-unknown` (declarative, [source](../../probes/salesforce/api-version-retired-or-unknown.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/limits"},"error":{"status":410,"body_excerpt":"the requested resource no longer exists."}}'
```

YAML: [facts/salesforce/retired-api-version-410.yaml](../../facts/salesforce/retired-api-version-410.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
