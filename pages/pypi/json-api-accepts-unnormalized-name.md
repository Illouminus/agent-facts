# GET /pypi/{project}/json with a non-normalized name such as Typing_Extensions returns HTTP 200 directly, without a redirect, and info.name is typing-extensions.

**PyPI (Python Package Index) · GET /pypi/{project}/json**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 25 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:pypi:probe:json-unnormalized-name` (declarative, [source](../../probes/pypi/json-unnormalized-name.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/json"}}'
```

YAML: [facts/pypi/json-api-accepts-unnormalized-name.yaml](../../facts/pypi/json-api-accepts-unnormalized-name.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
