# `not found`

**PyPI (Python Package Index) · GET /pypi/{project}/json · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 30 confirmations from 2 vantages

> GET /pypi/{project}/json for a project that does not exist returns HTTP 404 with the JSON body {"message": "Not Found"}.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:pypi:probe:json-not-found` (declarative, [source](../../probes/pypi/json-not-found.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/json"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/pypi/project-not-found-404.yaml](../../facts/pypi/project-not-found-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
