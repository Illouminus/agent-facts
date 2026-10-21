# GET /simple/{project}/ returns HTML unless Accept asks for application/vnd.pypi.simple.v1+json; the JSON form has name, versions and meta.\_last-serial, and Vary lists Accept.

**PyPI (Python Package Index) · GET /simple/{project}/**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-21 · 21 confirmations from 2 vantages

## What to do

1. Send header Accept = application/vnd.pypi.simple.v1+json.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:pypi:probe:simple-content-negotiation` (declarative, [source](../../probes/pypi/simple-content-negotiation.yaml)) · official doc: <https://docs.pypi.org/api/index-api/>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/simple/{project}/"}}'
```

YAML: [facts/pypi/simple-api-html-unless-accept-json.yaml](../../facts/pypi/simple-api-html-unless-accept-json.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
