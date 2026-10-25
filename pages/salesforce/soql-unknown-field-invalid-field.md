# `select nosuchfield__c from account ^ error at row:#:column:# no such column 'nosuchfield__c' on entity 'account'. if you are attempting to use a custom field, be sure to append the '__c' after the custom field name. please reference your wsdl or the describe call for the appropriate names.`

**Salesforce Platform REST API · GET /services/data/{version}/query · HTTP 400 `INVALID_FIELD`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-25 · 13 confirmations from 2 vantages

> A SOQL query naming a field the object does not have returns HTTP 400 INVALID_FIELD ("No such column '\<field\>' on entity '\<object\>'") with the row and column of the error.

## What to do

1. Call GET /services/data/{version}/sobjects/{object}/describe instead.

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:soql-unknown-field` (declarative, [source](../../probes/salesforce/soql-unknown-field.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/query"},"error":{"status":400,"body_excerpt":"select nosuchfield__c from account ^ error at row:#:column:# no such column '\''nosuchfield__c'\'' on entity '\''account'\''. if you are attempting to use a custom field, be sure to append the '\''__c'\'' after the custom field name. please reference your wsdl or the describe call for the appropriate names."}}'
```

YAML: [facts/salesforce/soql-unknown-field-invalid-field.yaml](../../facts/salesforce/soql-unknown-field-invalid-field.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
