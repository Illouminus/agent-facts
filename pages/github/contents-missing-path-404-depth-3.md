# `Not Found`

**GitHub REST API · GET /repos/{owner}/{repo}/contents/{dir}/{subdir}/{path} · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> An anonymous GET of a three-segment contents path that does not exist returns HTTP 404 Not Found; a missing parent directory gets the same 404, not a separate error.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:contents-not-found` (declarative, [source](../../probes/github/contents-not-found.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `not found`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}/contents/{dir}/{subdir}/{path}"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/github/contents-missing-path-404-depth-3.yaml](../../facts/github/contents-missing-path-404-depth-3.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
