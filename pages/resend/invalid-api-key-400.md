# `API key is invalid`

**Resend · GET /domains · HTTP 400 `validation_error`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> A request whose Bearer API key is not a valid key returns HTTP 400 validation_error "API key is invalid", not a 401 (a missing key is 401 missing_api_key), in the flat {statusCode, name, message} body with WWW-Authenticate: Bearer.

## What to do

1. Send header Authorization = the account setting bearer_api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:resend:probe:invalid-key` (declarative, [source](../../probes/resend/invalid-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `api key is invalid`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.resend.com/domains"},"error":{"status":400,"body_excerpt":"api key is invalid"}}'
```

YAML: [facts/resend/invalid-api-key-400.yaml](../../facts/resend/invalid-api-key-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
