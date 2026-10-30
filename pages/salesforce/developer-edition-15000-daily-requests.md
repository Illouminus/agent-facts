# A Developer Edition org allows 15,000 API requests a day: /limits reports DailyApiRequests.Max 15000 and its Remaining count.

**Salesforce Platform REST API · GET /services/data/{version}/limits · HTTP 200**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-30 · 93 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:daily-api-limit` (declarative, [source](../../probes/salesforce/daily-api-limit.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/limits"},"error":{"status":200}}'
```

YAML: [facts/salesforce/developer-edition-15000-daily-requests.yaml](../../facts/salesforce/developer-edition-15000-daily-requests.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
