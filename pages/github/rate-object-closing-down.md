# The rate object of GET /rate_limit is closing down; the resources.core object carries the same information.

**GitHub REST API · GET /rate_limit**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Send header X-GitHub-Api-Version = 2022-11-28.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.github.com/en/rest/rate-limit/rate-limit>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/rate_limit"}}'
```

YAML: [facts/github/rate-object-closing-down.yaml](../../facts/github/rate-object-closing-down.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
