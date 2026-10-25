# SOAP API login() is retired in Summer '27, stays available in API 64.0 and earlier until then, and is disabled by default in orgs created in Winter '26 or later.

**Salesforce Platform REST API · POST /services/Soap/u/{version}**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

official doc: <https://developer.salesforce.com/docs/platform/api/guide/sforce-api-calls-login.html>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://login.salesforce.com/services/Soap/u/{version}"}}'
```

YAML: [facts/salesforce/soap-login-retiring-summer-27.yaml](../../facts/salesforce/soap-login-retiring-summer-27.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
