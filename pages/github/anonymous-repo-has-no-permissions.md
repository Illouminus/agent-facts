# An anonymous GET /repos/{owner}/{repo} returns the repository object without a permissions field.

**GitHub REST API · GET /repos/{owner}/{repo}**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 13 confirmations from 2 vantages

## What to do

1. Request OAuth scope public_repo.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-anonymous` (declarative, [source](../../probes/github/repo-anonymous.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"}}'
```

YAML: [facts/github/anonymous-repo-has-no-permissions.yaml](../../facts/github/anonymous-repo-has-no-permissions.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
