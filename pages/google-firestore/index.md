# Cloud Firestore (Firebase) REST API

Hosts: `firestore.googleapis.com` · 18 facts

## Error meanings

- ✅ verified:server:prod · [`document "projects/agent-facts-probes/databases/(default)/documents/agent_facts/nosuch" not found.`](document-not-found-404.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod
- ✅ verified:server:prod · [``invalid property path "a b". unquoted property paths must match regex ([a-za-z_][a-za-z_#-#]*), and quoted property paths must match regex (`(?:[^`\\]|(?:\\.))+`)``](invalid-field-path-400.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection} · env prod
- ✅ verified:server:prod · [`page size must be nonnegative.`](negative-page-size-400.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection} · env prod
- ✅ verified:server:prod · [`the database agentfacts-nosuch-db does not exist for project agent-facts-probes please visit <url> to add a cloud datastore or cloud firestore database.`](unknown-database-404.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod

## Rate limits

- 🔵 official · [A document is at most 1 MiB (1,048,576 bytes), an API request at most 10 MiB, and subcollections nest at most 100 levels deep.](document-size-limit-1mib.md) · PATCH /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod
- 🔵 official · [The free quota is 50,000 document reads and 20,000 writes and 20,000 deletes per day, reset around midnight Pacific time.](free-quota-resets-midnight-pacific.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod

## Silent behavior

- ✅ verified:server:prod · [Arrays and maps are wrapped twice: an array is arrayValue.values\[\] of typed values (stringValue: "a"), a map is mapValue.fields.\<key\> holding a typed value.](array-and-map-values-are-wrapped.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod
- ✅ verified:server:prod · [Listing a collection that has no documents returns HTTP 200 with an empty object {}: no documents field (not documents: \[\]) and no nextPageToken.](empty-collection-returns-empty-object.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection} · env prod
- ✅ verified:server:prod · [In REST documents an integer field comes back as a JSON string (integerValue: "42", int64 format), while a double is a JSON number (doubleValue: 3.5).](integer-value-is-a-string.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod
- ✅ verified:server:prod · [A null field comes back as {nullValue: null}: the type key is present and its value is JSON null, so a field set to null is not the same as a missing field.](null-value-is-json-null.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod
- ✅ verified:server:prod · [orderBy on a field that no document has is accepted with HTTP 200 instead of being refused.](order-by-unknown-field-accepted.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection} · env prod
- ✅ verified:server:prod · [Listing a subcollection under a parent document that does not exist returns HTTP 200 {} rather than 404: the parent's absence is not reported.](subcollection-of-missing-document-is-empty.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document}/{subcollection} · env prod
- ✅ verified:server:prod · [A timestamp field comes back as timestampValue, an RFC 3339 string in UTC with a Z suffix ("2026-10-24T00:00:00Z").](timestamp-value-rfc3339-utc.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod

## Auth quirks

- 🔵 official · [Server client libraries bypass all Firestore security rules and authenticate with Application Default Credentials, so their access is decided by IAM, not by the rules.](server-access-bypasses-security-rules.md) · POST /v1/projects/{project}/databases/{database}/documents:runQuery · env prod
- ✅ verified:server:prod · [`document "projects/agent-facts-probes/databases/(default)/documents/agent_facts/nosuch" not found.`](unauthenticated-read-under-test-mode.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod
- ✅ verified:server:prod · [`permission denied on resource project agent-facts-nosuch-project-x.`](unknown-project-403.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod

## Pagination

- ✅ verified:server:prod · [`invalid page token`](invalid-page-token-400.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection} · env prod

## Schema drift

- ✅ verified:server:prod · [A REST document has exactly four top-level keys: name (the full resource path), fields, createTime and updateTime.](document-envelope-keys.md) · GET /v1/projects/{project}/databases/{database}/documents/{collection}/{document} · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
