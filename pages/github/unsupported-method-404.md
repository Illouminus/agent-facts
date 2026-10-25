# A request with an HTTP method the endpoint does not support, such as DELETE on a GET-only endpoint, returns HTTP 404 Not Found instead of 405 Method Not Allowed.

**GitHub REST API · DELETE /rate_limit · HTTP 404**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Call GET /rate_limit instead.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"DELETE","url":"https://api.github.com/rate_limit"},"error":{"status":404}}'
```

YAML: [facts/github/unsupported-method-404.yaml](../../facts/github/unsupported-method-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
