# `moved permanently`

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 301**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 10 confirmations from 2 vantages

> GET /repos/{owner}/{repo} on a renamed or transferred repository returns HTTP 301 Moved Permanently with Location /repositories/{id} instead of the repository object.

## What to do

1. Call GET /repositories/{id} instead.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-renamed` (declarative, [source](../../probes/github/repo-renamed.yaml)) · official doc: <https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#follow-redirects>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":301,"body_excerpt":"moved permanently"}}'
```

YAML: [facts/github/renamed-repo-301.yaml](../../facts/github/renamed-repo-301.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
