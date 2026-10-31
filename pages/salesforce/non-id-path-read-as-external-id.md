# `Provided external ID field does not exist or is not accessible: notanid`

**Salesforce Platform REST API · GET /services/data/{version}/sobjects/{object}/{id} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-31 · 320 confirmations from 2 vantages

> A record path whose last segment is not an id (…/sobjects/Account/notanid) is read as an external ID field name: HTTP 404 "Provided external ID field does not exist or is not accessible: notanid".

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:non-id-read-as-external-id` (declarative, [source](../../probes/salesforce/non-id-read-as-external-id.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `provided external id field does not exist or is not accessible: notanid`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/sobjects/{object}/{id}"},"error":{"status":404,"body_excerpt":"provided external id field does not exist or is not accessible: notanid"}}'
```

YAML: [facts/salesforce/non-id-path-read-as-external-id.yaml](../../facts/salesforce/non-id-path-read-as-external-id.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
