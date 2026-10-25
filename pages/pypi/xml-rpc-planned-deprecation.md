# The XML-RPC API is planned for deprecation and may be rate limited; no new integration should use it, and existing consumers should move to the JSON, RSS or Index APIs.

**PyPI (Python Package Index) · POST /pypi**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Call GET /pypi/{project}/json instead.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.pypi.org/api/#api-preference>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://pypi.org/pypi"}}'
```

YAML: [facts/pypi/xml-rpc-planned-deprecation.yaml](../../facts/pypi/xml-rpc-planned-deprecation.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
