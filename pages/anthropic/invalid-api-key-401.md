# `invalid x-api-key`

**Claude API (Anthropic) · GET /v1/models · HTTP 401 `authentication_error`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> A request whose x-api-key is not a valid key returns HTTP 401 authentication_error "invalid x-api-key", a different message from a missing header, with x-should-retry: false.

## What to do

1. Send header x-api-key = the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:anthropic:probe:invalid-key` (declarative, [source](../../probes/anthropic/invalid-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `invalid x-api-key`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.anthropic.com/v1/models"},"error":{"status":401,"body_excerpt":"invalid x-api-key"}}'
```

YAML: [facts/anthropic/invalid-api-key-401.yaml](../../facts/anthropic/invalid-api-key-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
