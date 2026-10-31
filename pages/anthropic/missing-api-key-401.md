# `x-api-key header is required`

**Claude API (Anthropic) · GET /v1/models · HTTP 401 `authentication_error`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> A request without an x-api-key header returns HTTP 401 authentication_error "x-api-key header is required" with the header x-should-retry: false.

## What to do

1. Send header x-api-key = the account setting api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:anthropic:probe:no-key` (declarative, [source](../../probes/anthropic/no-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `x-api-key header is required`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.anthropic.com/v1/models"},"error":{"status":401,"body_excerpt":"x-api-key header is required"}}'
```

YAML: [facts/anthropic/missing-api-key-401.yaml](../../facts/anthropic/missing-api-key-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
