# info.downloads in the JSON API is deprecated: last_day, last_week and last_month are always -1, and bugtrack_url is always null.

**PyPI (Python Package Index) · GET /pypi/{project}/json**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-21 · 21 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous · also seen: [any](releases-key-deprecated.md) (official 2026-10-20)

## Evidence

Probe `af:pypi:probe:json-project` (declarative, [source](../../probes/pypi/json-project.yaml)) · official doc: <https://docs.pypi.org/api/json/#get-a-project>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/json"}}'
```

YAML: [facts/pypi/downloads-always-minus-one.yaml](../../facts/pypi/downloads-always-minus-one.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
