# `Your API key was reported as leaked. Please use another API key.`

**Gemini API · POST /v1beta/models/{model_and_method} · HTTP 403 `PERMISSION_DENIED`**

Status: 🔵 official · first seen 2026-10-24

> A key that Google has detected as leaked is blocked: requests return HTTP 403 PERMISSION_DENIED "Your API key was reported as leaked. Please use another API key.".

## What to do

1. A human must enable new_api_key in the vendor dashboard (see https://ai.google.dev/gemini-api/docs/troubleshooting).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://ai.google.dev/gemini-api/docs/troubleshooting>

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `your api key was reported as leaked. please use another api key.`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://generativelanguage.googleapis.com/v1beta/models/{model_and_method}"},"error":{"status":403,"body_excerpt":"your api key was reported as leaked. please use another api key."}}'
```

YAML: [facts/google-gemini/leaked-key-403.yaml](../../facts/google-gemini/leaked-key-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
