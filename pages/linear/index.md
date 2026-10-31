# Linear API

Hosts: `api.linear.app` · 4 facts

## Error meanings

- ✅ verified:server:prod · [`This operation has been blocked as a potential Cross-Site Request Forgery (CSRF). Please either specify a 'content-type' header (with a type that is not one of application/x-www-form-urlencoded, multipart/form-data, text/plain) or provide a non-empty value for one of the following headers: x-apollo-operation-name, apollo-require-preflight`](graphql-get-csrf-400.md) · GET /graphql · env prod

## Silent behavior

- ✅ verified:server:prod · [Errors are a GraphQL body {errors: \[{message, extensions: {code, type, statusCode, userError, userPresentableMessage, http}}\]} sent with a matching HTTP status; the vendor code is errors\[0\].extensions.code and the request id comes in the x-request-id header.](error-envelope.md) · GET /graphql · env prod

## Auth quirks

- ✅ verified:server:prod · [`Authentication required, not authenticated`](invalid-api-key-same-as-missing.md) · GET /graphql · env prod
- ✅ verified:server:prod · [`Authentication required, not authenticated`](missing-api-key-401.md) · GET /graphql · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
