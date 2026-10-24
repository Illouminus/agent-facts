# `invalid json payload received. unknown name "agent_facts_unknown": cannot bind query parameter. field 'agent_facts_unknown' could not be found in request message.`

**Gemini API · GET /v1beta/models · HTTP 400 `INVALID_ARGUMENT`**

Status: ✅ verified:server:prod · first seen 2026-10-24 · last confirmed 2026-10-24 · 1 confirmation from 1 vantage

> An unknown query parameter returns HTTP 400 INVALID_ARGUMENT ("Cannot bind query parameter") instead of being ignored.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

Probe `af:google-gemini:probe:unknown-query-parameter` (declarative, [source](../../probes/google-gemini/unknown-query-parameter.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://generativelanguage.googleapis.com/v1beta/models"},"error":{"status":400,"body_excerpt":"invalid json payload received. unknown name \"agent_facts_unknown\": cannot bind query parameter. field '\''agent_facts_unknown'\'' could not be found in request message."}}'
```

YAML: [facts/google-gemini/unknown-query-parameter-400.yaml](../../facts/google-gemini/unknown-query-parameter-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
