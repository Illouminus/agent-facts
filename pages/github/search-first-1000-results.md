# `only the first #### search results are available`

**GitHub REST API · GET /search/repositories · HTTP 422**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-23 · 41 confirmations from 2 vantages

> Search returns at most 1,000 results per query: a page past them (per_page 100, page 11) returns HTTP 422 Only the first 1000 search results are available.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:search-beyond-1000` (declarative, [source](../../probes/github/search-beyond-1000.yaml)) · official doc: <https://docs.github.com/en/rest/search/search#about-search>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/search/repositories"},"error":{"status":422,"body_excerpt":"only the first #### search results are available"}}'
```

YAML: [facts/github/search-first-1000-results.yaml](../../facts/github/search-first-1000-results.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
