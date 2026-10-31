# `unexpected token: '<redacted>'`

**Salesforce Platform REST API · GET /services/data/{version}/query · HTTP 400 `MALFORMED_QUERY`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-31 · 109 confirmations from 2 vantages

> A SOQL query with a syntax error returns HTTP 400 MALFORMED_QUERY naming the unexpected token ("unexpected token: 'SELEC'").

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:soql-malformed-query` (declarative, [source](../../probes/salesforce/soql-malformed-query.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/query"},"error":{"status":400,"body_excerpt":"unexpected token: '\''<redacted>'\''"}}'
```

YAML: [facts/salesforce/soql-malformed-query-400.yaml](../../facts/salesforce/soql-malformed-query-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
