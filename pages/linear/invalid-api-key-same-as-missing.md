# `Authentication required, not authenticated`

**Linear API · GET /graphql · HTTP 401 `AUTHENTICATION_ERROR`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> An Authorization value that is not a valid key returns exactly what no key returns: HTTP 401 AUTHENTICATION_ERROR "Authentication required, not authenticated". Linear has no separate invalid-key error, so this 401 does not tell a wrong key from a missing one.

## What to do

1. Send header Authorization = the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:linear:probe:invalid-key` (declarative, [source](../../probes/linear/invalid-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `authentication required, not authenticated`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.linear.app/graphql"},"error":{"status":401,"body_excerpt":"authentication required, not authenticated"}}'
```

YAML: [facts/linear/invalid-api-key-same-as-missing.yaml](../../facts/linear/invalid-api-key-same-as-missing.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
