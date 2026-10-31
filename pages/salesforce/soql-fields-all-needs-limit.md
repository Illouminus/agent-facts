# `The SOQL FIELDS function must have a LIMIT of at most 200`

**Salesforce Platform REST API · GET /services/data/{version}/query · HTTP 400 `MALFORMED_QUERY`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-31 · 109 confirmations from 2 vantages

> SELECT FIELDS(ALL) without a LIMIT returns HTTP 400 MALFORMED_QUERY "The SOQL FIELDS function must have a LIMIT of at most 200".

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:soql-fields-all-needs-limit` (declarative, [source](../../probes/salesforce/soql-fields-all-needs-limit.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `the soql fields function must have a limit of at most ###`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/query"},"error":{"status":400,"body_excerpt":"the soql fields function must have a limit of at most ###"}}'
```

YAML: [facts/salesforce/soql-fields-all-needs-limit.yaml](../../facts/salesforce/soql-fields-all-needs-limit.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
