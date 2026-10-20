# `not found`

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-20 · 1 confirmation from 1 vantage

> GET /repos/{owner}/{repo} returns HTTP 404 Not Found both for a repository that does not exist and for a private one requested without valid authentication, never 403.

## What to do

1. Request OAuth scope repo.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-not-found` (declarative, [source](../../probes/github/repo-not-found.yaml)) · official doc: <https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/github/missing-or-private-repo-404.yaml](../../facts/github/missing-or-private-repo-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
