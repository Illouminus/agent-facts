# Requests without X-GitHub-Api-Version use version 2022-11-28, supported until 2028-03-10; after that, unversioned requests move to the next oldest supported version.

**GitHub REST API · GET /repos/{owner}/{repo}**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Send header X-GitHub-Api-Version = 2026-03-10.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.github.com/en/rest/about-the-rest-api/api-versions#supported-api-versions>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"}}'
```

YAML: [facts/github/default-api-version-end-of-support.yaml](../../facts/github/default-api-version-end-of-support.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
