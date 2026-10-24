# `this property cannot be expanded (data.agent_facts).`

**Stripe API · GET /v1/customers · HTTP 400**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 1 confirmation from 1 vantage

> An expand\[\] path that is not expandable returns HTTP 400 invalid_request_error without an error code; the message quotes the path.

## What to do

1. Omit query parameter expand.

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:expand-not-expandable` (declarative, [source](../../probes/stripe/expand-not-expandable.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"},"error":{"status":400,"body_excerpt":"this property cannot be expanded (data.agent_facts)."}}'
```

YAML: [facts/stripe/expand-not-expandable.yaml](../../facts/stripe/expand-not-expandable.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
