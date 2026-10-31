# `session expired or invalid`

**Salesforce Platform REST API · GET /services/data/{version}/limits · HTTP 401 `INVALID_SESSION_ID`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-31 · 179 confirmations from 2 vantages

> A REST call with no access token returns HTTP 401 \[{errorCode: INVALID_SESSION_ID, message: "Session expired or invalid"}\].

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:versions-without-session` (declarative, [source](../../probes/salesforce/versions-without-session.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/limits"},"error":{"status":401,"body_excerpt":"session expired or invalid"}}'
```

YAML: [facts/salesforce/missing-session-401.yaml](../../facts/salesforce/missing-session-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
