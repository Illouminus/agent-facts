# example-sdk 2.x calls the v1 endpoints, which stop accepting requests on 2027-01-01.

**Example API · SDK `example-sdk` (pypi) `>=2,<3`**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Upgrade example-sdk (pypi) to ≥ 3.0.0.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.example.com/sdk/migration-v3>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"url":"pypi:example-sdk"}}'
```

YAML: [facts/example/sdk-v2-legacy-endpoint.yaml](../../facts/example/sdk-v2-legacy-endpoint.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
