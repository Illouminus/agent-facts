# With X-GitHub-Api-Version 2026-03-10, GET /repos/{owner}/{repo} no longer returns has_downloads, which the default version 2022-11-28 still includes.

**GitHub REST API · GET /repos/{owner}/{repo}**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 9 confirmations from 2 vantages

## What to do

1. Send header X-GitHub-Api-Version = 2022-11-28.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-api-version-2026` (declarative, [source](../../probes/github/repo-api-version-2026.yaml)) · official doc: <https://docs.github.com/en/rest/about-the-rest-api/breaking-changes>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"}}'
```

YAML: [facts/github/api-version-2026-drops-has-downloads.yaml](../../facts/github/api-version-2026-drops-has-downloads.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
