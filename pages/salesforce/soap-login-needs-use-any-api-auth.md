# Where login() is restricted (the default in new orgs), a user without the Use Any API Auth permission gets INSUFFICIENT_ACCESS from login().

**Salesforce Platform REST API · POST /services/Soap/u/{version} · `INSUFFICIENT_ACCESS`**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. A human must enable use_any_api_auth in the vendor dashboard (see https://developer.salesforce.com/docs/platform/api/guide/sforce-api-calls-login.html).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

official doc: <https://developer.salesforce.com/docs/platform/api/guide/sforce-api-calls-login.html>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://login.salesforce.com/services/Soap/u/{version}"}}'
```

YAML: [facts/salesforce/soap-login-needs-use-any-api-auth.yaml](../../facts/salesforce/soap-login-needs-use-any-api-auth.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
