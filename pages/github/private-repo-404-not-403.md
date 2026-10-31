# `Not Found`

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 404**

Status: 🔵 official · first seen 2026-10-20

> A request for a private resource without proper authentication returns 404 Not Found, not 403 Forbidden, so that the existence of private repositories is not confirmed.

## What to do

1. Request OAuth scope repo.

## In your code

When an SDK receives this response:

| SDK | Raises | Check |
| --- | --- | --- |
| Python `PyGithub` (community) | `github.UnknownObjectException` | `e.status == 404` |
| Node `@octokit/request` | `RequestError` | `err.status === 404` |

Read from the SDK source: PyGithub 2.10.0: github/Requester.py Requester.createException; @octokit/request 10.0.16: dist-bundle/index.js fetchWrapper; @octokit/request-error 7.1.2.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource>

Observations: none from reporters yet.

## Related errors

- [REST error bodies carry a status field holding the HTTP code as a JSON string, such as "404", not as a number.](error-status-is-a-string.md) · GET /repos/{owner}/{repo} · HTTP 404
- [`Not Found`](missing-repo-404.md) · GET /repos/{owner}/{repo} · HTTP 404
- [`Not Found`](contents-missing-path-404.md) · GET /repos/{owner}/{repo}/contents/{path} · HTTP 404
- [`Not Found`](contents-missing-path-404-depth-2.md) · GET /repos/{owner}/{repo}/contents/{dir}/{path} · HTTP 404
- [`Not Found`](contents-missing-path-404-depth-3.md) · GET /repos/{owner}/{repo}/contents/{dir}/{subdir}/{path} · HTTP 404
- [`Not Found`](contents-missing-path-404-depth-4.md) · GET /repos/{owner}/{repo}/contents/{dir}/{subdir}/{subdir2}/{path} · HTTP 404

## Machine access

Match signature (what `check()` matches): `not found`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":404,"body_excerpt":"not found"}}'
```

YAML: [facts/github/private-repo-404-not-403.yaml](../../facts/github/private-repo-404-not-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
