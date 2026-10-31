# `Missing bearer authentication in header`

**OpenAI API · GET /v1/models · HTTP 401 `invalid_request_error`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> A request without an Authorization header returns HTTP 401 "Missing bearer authentication in header" with error.type invalid_request_error and error.code null (an invalid key has code invalid_api_key), plus WWW-Authenticate: Bearer realm="OpenAI API".

## What to do

1. Send header Authorization = the account setting bearer_api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:openai:probe:no-key` (declarative, [source](../../probes/openai/no-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `missing bearer authentication in header`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.openai.com/v1/models"},"error":{"status":401,"body_excerpt":"missing bearer authentication in header"}}'
```

YAML: [facts/openai/missing-api-key-401.yaml](../../facts/openai/missing-api-key-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
