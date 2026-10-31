# GitHub REST API

Hosts: `api.github.com` · 23 facts

## Error meanings

- ✅ verified:server:prod · [`Not Found`](missing-repo-404.md) · GET /repos/{owner}/{repo} · env prod
- ✅ verified:server:prod · [`The search is longer than 256 characters.`](search-query-longer-than-256.md) · GET /search/repositories · env prod
- ✅ verified:server:prod · [`404 Not Found`](trailing-slash-404.md) · GET /rate_limit/ · env prod
- ✅ verified:server:prod · [`The version you specified in the "X-GitHub-API-Version" request header, "2021-01-01", is not a supported version. The following versions are currently supported: "2026-03-10" (most recent) and "2022-11-28".`](unsupported-api-version-400.md) · GET /repos/{owner}/{repo} · env prod
- 🔵 official · [A request with an HTTP method the endpoint does not support, such as DELETE on a GET-only endpoint, returns HTTP 404 Not Found instead of 405 Method Not Allowed.](unsupported-method-404.md) · DELETE /rate_limit · env prod

## Rate limits

- ✅ verified:server:prod · [Anonymous REST requests count against the core resource with x-ratelimit-limit 60 per hour, shared by every client behind the same originating IP address.](anonymous-core-rate-limit.md) · GET /repos/{owner}/{repo} · env prod
- ✅ verified:server:prod · [Anonymous calls to the search endpoints count against a separate search resource with x-ratelimit-limit 10 (documented as 10 requests per minute), not against core.](anonymous-search-rate-limit.md) · GET /search/repositories · env prod
- 🔵 official · [Exceeding a secondary rate limit returns HTTP 403 or 429 with a message saying so; retry-after, when present, gives the seconds to wait, otherwise the wait is at least one minute.](secondary-rate-limit.md) · GET /repos/{owner}/{repo} · env prod
- 🔵 official · [Exceeding a secondary rate limit returns HTTP 403 or 429 with a message saying so; retry-after, when present, gives the seconds to wait, otherwise the wait is at least one minute.](secondary-rate-limit-429.md) · GET /repos/{owner}/{repo} · env prod

## Breaking changes

- ✅ verified:server:prod · [With X-GitHub-Api-Version 2026-03-10, GET /repos/{owner}/{repo} no longer returns has_downloads, which the default version 2022-11-28 still includes.](api-version-2026-drops-has-downloads.md) · GET /repos/{owner}/{repo} · env prod

## Silent behavior

- ✅ verified:server:prod · [Anonymous GET /repos/{owner}/{repo} responses are shared-cacheable for 60 s (public, s-maxage=60) and Vary does not list X-GitHub-Api-Version, so by HTTP caching rules a cache may serve a body of another API version.](anonymous-cache-ignores-api-version.md) · GET /repos/{owner}/{repo} · env prod
- ✅ verified:server:prod · [REST error bodies carry a status field holding the HTTP code as a JSON string, such as "404", not as a number.](error-status-is-a-string.md) · GET /repos/{owner}/{repo} · env prod
- ✅ verified:server:prod · [A per_page above 100 on GET /users/{username}/followers is silently reduced to 100: HTTP 200 with 100 items, no error, and Link URLs that repeat the requested per_page.](per-page-silently-capped-at-100.md) · GET /users/{username}/followers · env prod
- ✅ verified:server:prod · [`Moved Permanently`](renamed-repo-301.md) · GET /repos/{owner}/{repo} · env prod

## Auth quirks

- ✅ verified:server:prod · [An anonymous GET /repos/{owner}/{repo} returns the repository object without a permissions field.](anonymous-repo-has-no-permissions.md) · GET /repos/{owner}/{repo} · env prod
- ✅ verified:server:prod · [For anonymous callers GET /rate_limit reports a graphql resource limit of 0, so the GraphQL API has no anonymous quota, while REST core allows 60 requests per hour.](graphql-anonymous-limit-zero.md) · GET /rate_limit · env prod
- 🔵 official · [`Not Found`](private-repo-404-not-403.md) · GET /repos/{owner}/{repo} · env prod
- 🔵 official · [REST API requests without a User-Agent header are rejected, and a request with an invalid User-Agent header receives HTTP 403 Forbidden.](user-agent-required.md) · GET /repos/{owner}/{repo} · env prod

## Pagination

- ✅ verified:server:prod · [List endpoints such as GET /users/{username}/followers return a bare JSON array and give the next and last page URLs only in the Link header (rel="next", rel="last").](pagination-in-link-header.md) · GET /users/{username}/followers · env prod
- ✅ verified:server:prod · [`Only the first 1000 search results are available`](search-first-1000-results.md) · GET /search/repositories · env prod

## Deprecations

- 🔵 official · [Requests without X-GitHub-Api-Version use version 2022-11-28, supported until 2028-03-10; after that, unversioned requests move to the next oldest supported version.](default-api-version-end-of-support.md) · GET /repos/{owner}/{repo} · env prod
- 🔵 official · [The rate object of GET /rate_limit is closing down; the resources.core object carries the same information.](rate-object-closing-down.md) · GET /rate_limit · env prod

## Schema drift

- ✅ verified:server:prod · [On 2026-10-20 the repository object of GET /repos/{owner}/{repo} at API version 2022-11-28 had 84 top-level keys, schema fingerprint 4ca5975282230619.](repository-object-fingerprint.md) · GET /repos/{owner}/{repo} · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
