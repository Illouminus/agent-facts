# `version not found: 0.0.99`

**npm registry · GET /{package}/{version} · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> GET /{package}/{version} for an existing package with an unknown version or dist-tag returns HTTP 404 whose body is a bare JSON string "version not found: \<version\>", not an object.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:npm-registry:probe:version-not-found` (declarative, [source](../../probes/npm-registry/version-not-found.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `version not found: #.#.##`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://registry.npmjs.org/{package}/{version}"},"error":{"status":404,"body_excerpt":"version not found: #.#.##"}}'
```

YAML: [facts/npm-registry/version-not-found-404.yaml](../../facts/npm-registry/version-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
