# Errors are a JSON object {type: "error", error: {type, message}, request_id}; the vendor code is error.type (e.g. authentication_error) and the request id also comes in the request-id header.

**Claude API (Anthropic) · GET /v1/models · HTTP 401**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:anthropic:probe:no-key` (declarative, [source](../../probes/anthropic/no-key.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.anthropic.com/v1/models"},"error":{"status":401}}'
```

YAML: [facts/anthropic/error-envelope.yaml](../../facts/anthropic/error-envelope.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
