# `Not Found`

**npm registry · GET /{package}/{version} · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> GET /{package}/{version} for a package that does not exist returns HTTP 404 with the bare JSON string "Not Found"; an unencoded scoped name (/@scope/name) lands on the same path shape and returns {"error": "Not found"}.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:npm-registry:probe:missing-package-two-segments` (declarative, [source](../../probes/npm-registry/missing-package-two-segments.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `not found`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://registry.npmjs.org/{package}/{version}"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/npm-registry/missing-package-version-path-404.yaml](../../facts/npm-registry/missing-package-version-path-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
