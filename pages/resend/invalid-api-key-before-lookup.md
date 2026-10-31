# `API key is invalid`

**Resend · GET /emails/{email_id} · HTTP 400 `validation_error`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> GET /emails/{email_id} with an invalid API key returns HTTP 400 validation_error "API key is invalid" even for an id that does not exist: the key is checked before the email is looked up, so the 400 says nothing about the id.

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
  -d '{"target":{"method":"GET","url":"https://api.resend.com/emails/{email_id}"},"error":{"status":400,"body_excerpt":"api key is invalid"}}'
```

YAML: [facts/resend/invalid-api-key-before-lookup.yaml](../../facts/resend/invalid-api-key-before-lookup.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
