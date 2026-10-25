# `not found`

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 404**

Status: 🔵 official · first seen 2026-10-20

> A request for a private resource without proper authentication returns 404 Not Found, not 403 Forbidden, so that the existence of private repositories is not confirmed.

## What to do

1. Request OAuth scope repo.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/github/private-repo-404-not-403.yaml](../../facts/github/private-repo-404-not-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
