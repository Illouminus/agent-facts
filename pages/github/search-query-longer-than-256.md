# `the search is longer than ### characters.`

**GitHub REST API · GET /search/repositories · HTTP 422 `invalid`**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-30 · 156 confirmations from 2 vantages

> A search q parameter longer than 256 characters returns HTTP 422 Validation Failed with errors\[0\] code invalid, field q and message The search is longer than 256 characters.

## What to do

1. Keep q ≤ 256 bytes.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:search-query-too-long` (declarative, [source](../../probes/github/search-query-too-long.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/search/repositories"},"error":{"status":422,"body_excerpt":"the search is longer than ### characters."}}'
```

YAML: [facts/github/search-query-longer-than-256.yaml](../../facts/github/search-query-longer-than-256.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
