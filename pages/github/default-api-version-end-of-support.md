# Requests without X-GitHub-Api-Version use version 2022-11-28, supported until 2028-03-10; after that, unversioned requests move to the next oldest supported version.

**GitHub REST API · GET /repos/{owner}/{repo}**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Send header X-GitHub-Api-Version = 2026-03-10.

## In your code

Fix 1:

```python
headers["X-GitHub-Api-Version"] = "2026-03-10"
```

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.github.com/en/rest/about-the-rest-api/api-versions#supported-api-versions>

Observations: none from reporters yet.

## Related errors

- [REST error bodies carry a status field holding the HTTP code as a JSON string, such as "404", not as a number.](error-status-is-a-string.md) · GET /repos/{owner}/{repo} · HTTP 404
- [`Not Found`](missing-repo-404.md) · GET /repos/{owner}/{repo} · HTTP 404
- [`Not Found`](private-repo-404-not-403.md) · GET /repos/{owner}/{repo} · HTTP 404
- [Exceeding a secondary rate limit returns HTTP 403 or 429 with a message saying so; retry-after, when present, gives the seconds to wait, otherwise the wait is at least one minute.](secondary-rate-limit.md) · GET /repos/{owner}/{repo} · HTTP 403
- [Exceeding a secondary rate limit returns HTTP 403 or 429 with a message saying so; retry-after, when present, gives the seconds to wait, otherwise the wait is at least one minute.](secondary-rate-limit-429.md) · GET /repos/{owner}/{repo} · HTTP 429
- [`The version you specified in the "X-GitHub-API-Version" request header, "2021-01-01", is not a supported version. The following versions are currently supported: "2026-03-10" (most recent) and "2022-11-28".`](unsupported-api-version-400.md) · GET /repos/{owner}/{repo} · HTTP 400

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"}}'
```

YAML: [facts/github/default-api-version-end-of-support.yaml](../../facts/github/default-api-version-end-of-support.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
