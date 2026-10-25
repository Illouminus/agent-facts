# Exceeding a secondary rate limit returns HTTP 403 or 429 with a message saying so; retry-after, when present, gives the seconds to wait, otherwise the wait is at least one minute.

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 403**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Wait the number of seconds in Retry-After, then retry (≤ 3 attempts).
2. Retry with exponential backoff from 60000 ms × 2, cap 960000 ms, ≤ 5 attempts, with jitter.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api#exceeding-the-rate-limit>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":403}}'
```

YAML: [facts/github/secondary-rate-limit.yaml](../../facts/github/secondary-rate-limit.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
