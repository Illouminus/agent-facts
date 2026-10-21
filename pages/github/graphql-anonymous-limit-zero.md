# For anonymous callers GET /rate_limit reports a graphql resource limit of 0, so the GraphQL API has no anonymous quota, while REST core allows 60 requests per hour.

**GitHub REST API · GET /rate_limit**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-21 · 22 confirmations from 2 vantages

## What to do

1. Request OAuth scope public_repo.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:rate-limit` (declarative, [source](../../probes/github/rate-limit.yaml)) · official doc: <https://docs.github.com/en/rest/rate-limit/rate-limit>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/rate_limit"}}'
```

YAML: [facts/github/graphql-anonymous-limit-zero.yaml](../../facts/github/graphql-anonymous-limit-zero.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
