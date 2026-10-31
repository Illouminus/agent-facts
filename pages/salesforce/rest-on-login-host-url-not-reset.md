# `Destination URL not reset. The URL returned from login must be set`

**Salesforce Platform REST API · GET /services/data/{version}/limits · HTTP 400 `URL_NOT_RESET`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-31 · 179 confirmations from 2 vantages

> REST calls sent to login.salesforce.com instead of the org's instance return HTTP 400 URL_NOT_RESET "Destination URL not reset. The URL returned from login must be set", even /services/data.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:rest-on-login-host` (declarative, [source](../../probes/salesforce/rest-on-login-host.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `destination url not reset. the url returned from login must be set`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/limits"},"error":{"status":400,"body_excerpt":"destination url not reset. the url returned from login must be set"}}'
```

YAML: [facts/salesforce/rest-on-login-host-url-not-reset.yaml](../../facts/salesforce/rest-on-login-host-url-not-reset.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
