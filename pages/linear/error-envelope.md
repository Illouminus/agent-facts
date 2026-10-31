# Errors are a GraphQL body {errors: \[{message, extensions: {code, type, statusCode, userError, userPresentableMessage, http}}\]} sent with a matching HTTP status; the vendor code is errors\[0\].extensions.code and the request id comes in the x-request-id header.

**Linear API · GET /graphql · HTTP 401**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:linear:probe:no-key` (declarative, [source](../../probes/linear/no-key.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.linear.app/graphql"},"error":{"status":401}}'
```

YAML: [facts/linear/error-envelope.yaml](../../facts/linear/error-envelope.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
