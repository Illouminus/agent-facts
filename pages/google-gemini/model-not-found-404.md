# `model is not found: models/gemini-agent-facts-nosuch for api version v#beta`

**Gemini API · GET /v1beta/models/{model} · HTTP 404 `NOT_FOUND`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 14 confirmations from 2 vantages

> An unknown model name returns HTTP 404 NOT_FOUND with the message "Model is not found: models/\<name\> for api version v1beta".

## What to do

1. Call GET /v1beta/models instead.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:model-not-found` (declarative, [source](../../probes/google-gemini/model-not-found.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models/{model}"},"error":{"status":404,"body_excerpt":"model is not found: models/gemini-agent-facts-nosuch for api version v#beta"}}'
```

YAML: [facts/google-gemini/model-not-found-404.yaml](../../facts/google-gemini/model-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
