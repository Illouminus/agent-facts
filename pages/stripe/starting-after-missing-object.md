# `no such customer: 'cus_agentfactsnosuch'`

**Stripe API · GET /v1/customers · HTTP 400 `resource_missing`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 2 confirmations from 1 vantage

> A list cursor starting_after naming an object that does not exist returns HTTP 400 resource_missing with error.param starting_after, not an empty page.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:starting-after-missing` (declarative, [source](../../probes/stripe/starting-after-missing.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"},"error":{"status":400,"body_excerpt":"no such customer: '\''cus_agentfactsnosuch'\''"}}'
```

YAML: [facts/stripe/starting-after-missing-object.yaml](../../facts/stripe/starting-after-missing-object.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
