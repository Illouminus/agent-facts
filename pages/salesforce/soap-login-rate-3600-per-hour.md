# login() is limited to 3,600 calls per user per hour; past it the call fails with "Login Rate Exceeded" and the user is blocked from logging in for an hour.

**Salesforce Platform REST API · POST /services/Soap/u/{version}**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 60000 ms × 2, cap 3600000 ms, ≤ 3 attempts, with jitter.

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

YAML: [facts/salesforce/soap-login-rate-3600-per-hour.yaml](../../facts/salesforce/soap-login-rate-3600-per-hour.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
