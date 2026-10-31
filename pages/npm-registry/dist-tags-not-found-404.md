# `Not Found`

**npm registry · GET /-/package/{package}/dist-tags · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> GET /-/package/{package}/dist-tags for a package that does not exist returns HTTP 404 with the bare JSON string "Not Found", not an error object.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:npm-registry:probe:dist-tags-not-found` (declarative, [source](../../probes/npm-registry/dist-tags-not-found.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `not found`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://registry.npmjs.org/-/package/{package}/dist-tags"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/npm-registry/dist-tags-not-found-404.yaml](../../facts/npm-registry/dist-tags-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
