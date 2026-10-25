# Anonymous GET /repos/{owner}/{repo} responses are shared-cacheable for 60 s (public, s-maxage=60) and Vary does not list X-GitHub-Api-Version, so by HTTP caching rules a cache may serve a body of another API version.

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-24 · 24 confirmations from 2 vantages

## What to do

1. Set query parameter cb to new UUID per request.
2. Request OAuth scope public_repo.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-cache-headers` (declarative, [source](../../probes/github/repo-cache-headers.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":200}}'
```

YAML: [facts/github/anonymous-cache-ignores-api-version.yaml](../../facts/github/anonymous-cache-ignores-api-version.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
