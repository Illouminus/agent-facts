# GET /pypi/{project}/{version}/json no longer has the releases key; the files of every release are only on /pypi/{project}/json and the Index API.

**PyPI (Python Package Index) · GET /pypi/{project}/{version}/json**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-25 · 181 confirmations from 2 vantages

## What to do

1. Call GET /simple/{project}/ instead.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:pypi:probe:json-release` (declarative, [source](../../probes/pypi/json-release.yaml)) · official doc: <https://docs.pypi.org/api/json/#get-a-release>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/{version}/json"}}'
```

YAML: [facts/pypi/release-json-has-no-releases-key.yaml](../../facts/pypi/release-json-has-no-releases-key.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
