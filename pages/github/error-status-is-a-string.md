# REST error bodies carry a status field holding the HTTP code as a JSON string, such as "404", not as a number.

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 12 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-not-found` (declarative, [source](../../probes/github/repo-not-found.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":404}}'
```

YAML: [facts/github/error-status-is-a-string.yaml](../../facts/github/error-status-is-a-string.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
