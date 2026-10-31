# `No commit found for the ref agent-facts-no-such-ref`

**GitHub REST API · GET /repos/{owner}/{repo}/contents/{path} · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-31 · last confirmed 2026-10-31 · 1 confirmation from 1 vantage

> GET /repos/{owner}/{repo}/contents/{path}?ref=\<ref\> with a ref that names no branch, tag or commit returns HTTP 404 "No commit found for the ref \<ref\>", even when the path exists on the default branch.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:contents-unknown-ref` (declarative, [source](../../probes/github/contents-unknown-ref.yaml))

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `no commit found for the ref agent-facts-no-such-ref`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}/contents/{path}"},"error":{"status":404,"body_excerpt":"no commit found for the ref agent-facts-no-such-ref"}}'
```

YAML: [facts/github/contents-unknown-ref-404.yaml](../../facts/github/contents-unknown-ref-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
