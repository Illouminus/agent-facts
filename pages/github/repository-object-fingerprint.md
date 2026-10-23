# On 2026-10-20 the repository object of GET /repos/{owner}/{repo} at API version 2022-11-28 had 84 top-level keys, schema fingerprint 4ca5975282230619.

**GitHub REST API · GET /repos/{owner}/{repo}**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-23 · 14 confirmations from 2 vantages

## What to do

1. Send header X-GitHub-Api-Version = 2022-11-28.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-schema-fingerprint` (declarative, [source](../../probes/github/repo-schema-fingerprint.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"}}'
```

YAML: [facts/github/repository-object-fingerprint.yaml](../../facts/github/repository-object-fingerprint.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
