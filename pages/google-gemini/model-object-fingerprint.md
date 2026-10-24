# A model object from GET /v1beta/models/{model} has 12 top-level keys (description, displayName, inputTokenLimit, maxTemperature, name, outputTokenLimit, supportedGenerationMethods, temperature, thinking, topK, topP, version).

**Gemini API · GET /v1beta/models/{model} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 2 confirmations from 1 vantage

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:model-schema-fingerprint` (declarative, [source](../../probes/google-gemini/model-schema-fingerprint.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models/{model}"},"error":{"status":200}}'
```

YAML: [facts/google-gemini/model-object-fingerprint.yaml](../../facts/google-gemini/model-object-fingerprint.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
