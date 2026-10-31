# `Authentication required, not authenticated`

**Linear API · GET /graphql · HTTP 401 `AUTHENTICATION_ERROR`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> A query without an Authorization header returns HTTP 401 (not 200 with errors) and errors\[0\].extensions.code AUTHENTICATION_ERROR "Authentication required, not authenticated", before the query is resolved: an issue id that does not exist is the same 401.

## What to do

1. Send header Authorization = the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:linear:probe:no-key` (declarative, [source](../../probes/linear/no-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `authentication required, not authenticated`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.linear.app/graphql"},"error":{"status":401,"body_excerpt":"authentication required, not authenticated"}}'
```

YAML: [facts/linear/missing-api-key-401.yaml](../../facts/linear/missing-api-key-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
