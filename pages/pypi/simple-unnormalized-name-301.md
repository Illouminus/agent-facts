# GET /simple/{project}/ with a non-normalized name such as Typing_Extensions returns HTTP 301 to the PEP 503 normalized URL /simple/typing-extensions/.

**PyPI (Python Package Index) · GET /simple/{project}/ · HTTP 301**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 36 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:pypi:probe:simple-unnormalized-name` (declarative, [source](../../probes/pypi/simple-unnormalized-name.yaml)) · official doc: <https://docs.pypi.org/api/index-api/>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/simple/{project}/"},"error":{"status":301}}'
```

YAML: [facts/pypi/simple-unnormalized-name-301.yaml](../../facts/pypi/simple-unnormalized-name-301.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
