# Rate limits (requests per minute, input tokens per minute, requests per day) apply per Google Cloud project, not per API key: several keys of one project share them.

**Gemini API · POST /v1beta/models/{model_and_method}**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 1000 ms × 2, cap 60000 ms, ≤ 5 attempts, with jitter.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://ai.google.dev/gemini-api/docs/rate-limits>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://generativelanguage.googleapis.com/v1beta/models/{model_and_method}"}}'
```

YAML: [facts/google-gemini/rate-limits-per-project.yaml](../../facts/google-gemini/rate-limits-per-project.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
