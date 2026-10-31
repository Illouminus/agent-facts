# `Missing API Key`

**Resend · GET /domains · HTTP 401 `missing_api_key`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> A request without an API key returns HTTP 401 with the flat body {statusCode: 401, name: "missing_api_key", message: "Missing API Key"}: the error code is in name.

## What to do

1. Send header Authorization = the account setting bearer_api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:resend:probe:no-key` (declarative, [source](../../probes/resend/no-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `missing api key`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.resend.com/domains"},"error":{"status":401,"body_excerpt":"missing api key"}}'
```

YAML: [facts/resend/missing-api-key-401.yaml](../../facts/resend/missing-api-key-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
