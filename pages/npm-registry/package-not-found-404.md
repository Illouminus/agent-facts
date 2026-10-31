# `Not found`

**npm registry · GET /{package} · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> GET /{package} for a package that does not exist returns HTTP 404 with {"error": "Not found"}; a name spelled with uppercase letters (/Left-Pad) is the same 404, not a redirect to the lowercase package.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:npm-registry:probe:package-not-found` (declarative, [source](../../probes/npm-registry/package-not-found.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `not found`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://registry.npmjs.org/{package}"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/npm-registry/package-not-found-404.yaml](../../facts/npm-registry/package-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
