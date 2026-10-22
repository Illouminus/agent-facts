# On 2026-10-20 /pypi/{project}/json had the top-level keys info, last_serial, ownership, releases, urls and vulnerabilities, schema fingerprint f2ea8b7e27a470cf.

**PyPI (Python Package Index) · GET /pypi/{project}/json**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 29 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:pypi:probe:json-project-fingerprint` (declarative, [source](../../probes/pypi/json-project-fingerprint.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/json"}}'
```

YAML: [facts/pypi/project-json-fingerprint.yaml](../../facts/pypi/project-json-fingerprint.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
