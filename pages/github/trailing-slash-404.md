# `### not found`

**GitHub REST API · GET /rate_limit/ · HTTP 404**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-20 · 1 confirmation from 1 vantage

> A REST path with a trailing slash, such as /rate_limit/, returns HTTP 404 with the plain-text body 404 Not Found instead of the endpoint's JSON.

## What to do

1. Call GET /rate_limit instead.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:trailing-slash` (declarative, [source](../../probes/github/trailing-slash.yaml)) · official doc: <https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/rate_limit/"},"error":{"status":404,"body_excerpt":"### not found"}}'
```

YAML: [facts/github/trailing-slash-404.yaml](../../facts/github/trailing-slash-404.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
