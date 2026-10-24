# Authenticated REST responses such as /limits and a SOQL query carry Sforce-Limit-Info: api-usage=\<used\>/\<daily limit\> (…/15000 on a Developer Edition org).

**Salesforce Platform REST API · GET /services/data/{version}/limits · HTTP 200**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 3 confirmations from 1 vantage

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:daily-api-limit` (declarative, [source](../../probes/salesforce/daily-api-limit.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/limits"},"error":{"status":200}}'
```

YAML: [facts/salesforce/sforce-limit-info-header.yaml](../../facts/salesforce/sforce-limit-info-header.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
