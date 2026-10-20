# Anonymous REST requests count against the core resource with x-ratelimit-limit 60 per hour, shared by every client behind the same originating IP address.

**GitHub REST API · GET /repos/{owner}/{repo}**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-20 · 2 confirmations from 2 vantages

## What to do

1. Request OAuth scope public_repo.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-anonymous` (declarative, [source](../../probes/github/repo-anonymous.yaml)) · official doc: <https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api#primary-rate-limit-for-unauthenticated-users>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"}}'
```

YAML: [facts/github/anonymous-core-rate-limit.yaml](../../facts/github/anonymous-core-rate-limit.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
