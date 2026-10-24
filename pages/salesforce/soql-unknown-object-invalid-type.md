# `select id from nosuchobject__c ^ error at row:#:column:## sobject type 'nosuchobject__c' is not supported. if you are attempting to use a custom object, be sure to append the '__c' after the entity name. please reference your wsdl or the describe call for the appropriate names.`

**Salesforce Platform REST API · GET /services/data/{version}/query · HTTP 400 `INVALID_TYPE`**

Status: ✅ verified:server:sandbox · first seen 2026-10-24 · last confirmed 2026-10-24 · 3 confirmations from 1 vantage

> A SOQL query on an object the org does not have returns HTTP 400 INVALID_TYPE ("sObject type '\<object\>' is not supported").

## What to do

1. No client-side fix known (by design).

## Dimensions

env: sandbox · plan: any · region: any · account_state: developer_edition

## Evidence

Probe `af:salesforce:probe:soql-unknown-object` (declarative, [source](../../probes/salesforce/soql-unknown-object.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://login.salesforce.com/services/data/{version}/query"},"error":{"status":400,"body_excerpt":"select id from nosuchobject__c ^ error at row:#:column:## sobject type '\''nosuchobject__c'\'' is not supported. if you are attempting to use a custom object, be sure to append the '\''__c'\'' after the entity name. please reference your wsdl or the describe call for the appropriate names."}}'
```

YAML: [facts/salesforce/soql-unknown-object-invalid-type.yaml](../../facts/salesforce/soql-unknown-object-invalid-type.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
