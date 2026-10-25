# REST API requests without a User-Agent header are rejected, and a request with an invalid User-Agent header receives HTTP 403 Forbidden.

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 403**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Send header User-Agent = the account setting github_username.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api#user-agent>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":403}}'
```

YAML: [facts/github/user-agent-required.yaml](../../facts/github/user-agent-required.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
