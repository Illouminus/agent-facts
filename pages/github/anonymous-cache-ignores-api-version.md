# Anonymous GET /repos/{owner}/{repo} responses are publicly cached for 60 s and Vary omits X-GitHub-Api-Version, so a request can get a cached body of another API version; X-GitHub-Api-Version-Selected names the one served.

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-20 · 1 confirmation from 1 vantage

## What to do

1. Set query parameter cb to new UUID per request.
2. Request OAuth scope public_repo.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-anonymous` (declarative, [source](../../probes/github/repo-anonymous.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":200}}'
```

YAML: [facts/github/anonymous-cache-ignores-api-version.yaml](../../facts/github/anonymous-cache-ignores-api-version.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
