# `'text' query parameter is required`

**npm registry · GET /-/v1/search · HTTP 400 `ERR_TEXT_MISSING`**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> GET /-/v1/search without a text parameter, or with an empty one, returns HTTP 400 ERR_TEXT_MISSING ("'text' query parameter is required"), not an empty result list.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:npm-registry:probe:search-text-missing` (declarative, [source](../../probes/npm-registry/search-text-missing.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `'text' query parameter is required`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://registry.npmjs.org/-/v1/search"},"error":{"status":400,"body_excerpt":"'\''text'\'' query parameter is required"}}'
```

YAML: [facts/npm-registry/search-text-missing-400.yaml](../../facts/npm-registry/search-text-missing-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
