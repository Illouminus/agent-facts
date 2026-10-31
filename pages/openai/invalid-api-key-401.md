# `Incorrect API key provided: apifacts********-key. You can find your API key at https://platform.openai.com/account/api-keys.`

**OpenAI API · GET /v1/models · HTTP 401 `invalid_api_key`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> A request whose Bearer key is not a valid key returns HTTP 401 error.code invalid_api_key "Incorrect API key provided: …"; the message echoes the key masked (first 8 characters, asterisks, last 4), so the message differs per key while the code stays the same.

## What to do

1. Send header Authorization = the account setting bearer_api_key.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:openai:probe:invalid-key` (declarative, [source](../../probes/openai/invalid-key.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `incorrect api key provided: apifacts********-key. you can find your api key at <url>`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.openai.com/v1/models"},"error":{"status":401,"body_excerpt":"incorrect api key provided: apifacts********-key. you can find your api key at <url>"}}'
```

YAML: [facts/openai/invalid-api-key-401.yaml](../../facts/openai/invalid-api-key-401.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
