# `received unknown parameter: agent_facts_unknown`

**Stripe API · POST /v1/customers · HTTP 400 `parameter_unknown`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-26 · 7 confirmations from 2 vantages

> A 400 for a parameter that fails validation, such as parameter_unknown, is not saved under its Idempotency-Key: a retry with the same key is executed again and has no Idempotent-Replayed header.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: any

## Evidence

Probe `af:stripe:probe:validation-error-not-replayed` (declarative, [source](../../probes/stripe/validation-error-not-replayed.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/customers"},"error":{"status":400,"body_excerpt":"received unknown parameter: agent_facts_unknown"}}'
```

YAML: [facts/stripe/validation-errors-are-not-replayed.yaml](../../facts/stripe/validation-errors-are-not-replayed.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
