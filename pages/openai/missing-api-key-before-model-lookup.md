# `Missing bearer authentication in header`

**OpenAI API · GET /v1/models/{model} · HTTP 401 `invalid_request_error`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> GET /v1/models/{model} without an Authorization header returns HTTP 401 "Missing bearer authentication in header" even for a model id that does not exist: the key is checked before the model, so the 401 says nothing about the id.

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
  -d '{"target":{"method":"GET","url":"https://api.openai.com/v1/models/{model}"},"error":{"status":401,"body_excerpt":"missing bearer authentication in header"}}'
```

YAML: [facts/openai/missing-api-key-before-model-lookup.yaml](../../facts/openai/missing-api-key-before-model-lookup.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
