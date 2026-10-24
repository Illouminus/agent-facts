# Salesforce Platform REST API

Hosts: `login.salesforce.com`, `test.salesforce.com` · 18 facts

## Error meanings

- ✅ verified:server:sandbox · [`the requested resource does not exist`](record-not-found-404.md) · GET /services/data/{version}/sobjects/{object}/{id} · env sandbox
- ✅ verified:server:sandbox · [`destination url not reset. the url returned from login must be set`](rest-on-login-host-url-not-reset.md) · GET /services/data/{version}/limits · env sandbox
- ✅ verified:server:sandbox · [`the soql fields function must have a limit of at most ###`](soql-fields-all-needs-limit.md) · GET /services/data/{version}/query · env sandbox
- ✅ verified:server:sandbox · [`unexpected token: '<redacted>'`](soql-malformed-query-400.md) · GET /services/data/{version}/query · env sandbox
- ✅ verified:server:sandbox · [`select nosuchfield__c from account ^ error at row:#:column:# no such column 'nosuchfield__c' on entity 'account'. if you are attempting to use a custom field, be sure to append the '__c' after the custom field name. please reference your wsdl or the describe call for the appropriate names.`](soql-unknown-field-invalid-field.md) · GET /services/data/{version}/query · env sandbox
- ✅ verified:server:sandbox · [`select id from nosuchobject__c ^ error at row:#:column:## sobject type 'nosuchobject__c' is not supported. if you are attempting to use a custom object, be sure to append the '__c' after the entity name. please reference your wsdl or the describe call for the appropriate names.`](soql-unknown-object-invalid-type.md) · GET /services/data/{version}/query · env sandbox
- ✅ verified:server:sandbox · [`the requested resource does not exist`](unknown-sobject-describe-404.md) · GET /services/data/{version}/sobjects/{object}/describe · env sandbox

## Rate limits

- ✅ verified:server:sandbox · [A Developer Edition org allows 15,000 API requests a day: /limits reports DailyApiRequests.Max 15000 and its Remaining count.](developer-edition-15000-daily-requests.md) · GET /services/data/{version}/limits · env sandbox
- ✅ verified:server:sandbox · [Authenticated REST responses such as /limits and a SOQL query carry Sforce-Limit-Info: api-usage=\<used\>/\<daily limit\> (…/15000 on a Developer Edition org).](sforce-limit-info-header.md) · GET /services/data/{version}/limits · env sandbox
- 🔵 official · [login() is limited to 3,600 calls per user per hour; past it the call fails with "Login Rate Exceeded" and the user is blocked from logging in for an hour.](soap-login-rate-3600-per-hour.md) · POST /services/Soap/u/{version} · env sandbox

## Silent behavior

- ✅ verified:server:sandbox · [A SOQL query that matches nothing returns HTTP 200 with totalSize 0, done true and an empty records array, and no nextRecordsUrl.](empty-query-result-shape.md) · GET /services/data/{version}/query · env sandbox
- ✅ verified:server:sandbox · [REST errors are a JSON array of objects with errorCode and message (e.g. \[{errorCode: NOT_FOUND, …}\]), not a single error object.](errors-are-a-json-array.md) · GET /services/data/{version}/sobjects/{object}/{id} · env sandbox
- ✅ verified:server:sandbox · [`provided external id field does not exist or is not accessible: notanid`](non-id-path-read-as-external-id.md) · GET /services/data/{version}/sobjects/{object}/{id} · env sandbox

## Auth quirks

- ✅ verified:server:sandbox · [`session expired or invalid`](missing-session-401.md) · GET /services/data/{version}/limits · env sandbox
- 🔵 official · [Where login() is restricted (the default in new orgs), a user without the Use Any API Auth permission gets INSUFFICIENT_ACCESS from login().](soap-login-needs-use-any-api-auth.md) · POST /services/Soap/u/{version} · env sandbox
- ✅ verified:server:sandbox · [GET /services/data on the org's instance answers HTTP 200 with the list of API versions (version, url) without any credential, while /limits on the same host needs a session.](version-list-needs-no-session.md) · GET /services/data · env sandbox

## Deprecations

- ✅ verified:server:sandbox · [`the requested resource no longer exists.`](retired-api-version-410.md) · GET /services/data/{version}/limits · env sandbox
- 🔵 official · [SOAP API login() is retired in Summer '27, stays available in API 64.0 and earlier until then, and is disabled by default in orgs created in Winter '26 or later.](soap-login-retiring-summer-27.md) · POST /services/Soap/u/{version} · env sandbox

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
