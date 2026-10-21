# JSON API responses are CDN-cached with Cache-Control max-age=900 and carry ETag and X-PyPI-Last-Serial.

**PyPI (Python Package Index) · GET /pypi/{project}/json**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-21 · 11 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:pypi:probe:json-project` (declarative, [source](../../probes/pypi/json-project.yaml)) · official doc: <https://docs.pypi.org/api/#caching>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/json"}}'
```

YAML: [facts/pypi/json-api-cdn-cache.yaml](../../facts/pypi/json-api-cdn-cache.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
