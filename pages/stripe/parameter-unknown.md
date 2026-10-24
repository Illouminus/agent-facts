# `received unknown parameter: agent_facts_unknown`

**Stripe API · POST /v1/customers · HTTP 400 `parameter_unknown`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 1 confirmation from 1 vantage

> A form parameter the endpoint does not know returns HTTP 400 parameter_unknown, with the parameter name in error.param and in the message.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:parameter-unknown` (declarative, [source](../../probes/stripe/parameter-unknown.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/customers"},"error":{"status":400,"body_excerpt":"received unknown parameter: agent_facts_unknown"}}'
```

YAML: [facts/stripe/parameter-unknown.yaml](../../facts/stripe/parameter-unknown.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
