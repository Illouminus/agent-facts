# GET /pypi/{project}/json/ with a trailing slash returns HTTP 301 with a relative Location /pypi/{project}/json and an HTML body, not JSON.

**PyPI (Python Package Index) · GET /pypi/{project}/json/ · HTTP 301**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-21 · 69 confirmations from 2 vantages

## What to do

1. Call GET /pypi/{project}/json instead.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:pypi:probe:json-trailing-slash` (declarative, [source](../../probes/pypi/json-trailing-slash.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/json/"},"error":{"status":301}}'
```

YAML: [facts/pypi/json-trailing-slash-301.yaml](../../facts/pypi/json-trailing-slash-301.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
