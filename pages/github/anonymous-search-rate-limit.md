# Anonymous calls to the search endpoints count against a separate search resource with x-ratelimit-limit 10 (documented as 10 requests per minute), not against core.

**GitHub REST API · GET /search/repositories**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 26 confirmations from 2 vantages

## What to do

1. Retry with exponential backoff from 6000 ms × 2, cap 60000 ms, ≤ 5 attempts, with jitter.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:search-query-too-long` (declarative, [source](../../probes/github/search-query-too-long.yaml)) · official doc: <https://docs.github.com/en/rest/search/search#rate-limit>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/search/repositories"}}'
```

YAML: [facts/github/anonymous-search-rate-limit.yaml](../../facts/github/anonymous-search-rate-limit.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
