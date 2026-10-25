# PyPI's JSON, RSS and Index APIs are not rate limited at the edge because of heavy CDN caching, but PyPI may prohibit a consumer for irresponsible activity.

**PyPI (Python Package Index) · GET /pypi/{project}/json**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Send header User-Agent = the account setting contact_identifying_user_agent.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.pypi.org/api/#rate-limiting>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/json"}}'
```

YAML: [facts/pypi/no-edge-rate-limit.yaml](../../facts/pypi/no-edge-rate-limit.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
