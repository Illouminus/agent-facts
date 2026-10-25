# PyPI (Python Package Index)

Hosts: `pypi.org` · 16 facts

## Error meanings

- ✅ verified:server:prod · [`not found`](project-not-found-404.md) · GET /pypi/{project}/json · env prod
- ✅ verified:server:prod · [`not found`](release-not-found-404.md) · GET /pypi/{project}/{version}/json · env prod
- ✅ verified:server:prod · [`### not found`](simple-not-found-404.md) · GET /simple/{project}/ · env prod

## Rate limits

- 🔵 official · [PyPI's JSON, RSS and Index APIs are not rate limited at the edge because of heavy CDN caching, but PyPI may prohibit a consumer for irresponsible activity.](no-edge-rate-limit.md) · GET /pypi/{project}/json · env prod

## Breaking changes

- ✅ verified:server:prod · [GET /pypi/{project}/{version}/json no longer has the releases key; the files of every release are only on /pypi/{project}/json and the Index API.](release-json-has-no-releases-key.md) · GET /pypi/{project}/{version}/json · env prod

## Silent behavior

- ✅ verified:server:prod · [GET /pypi/{project}/json with a non-normalized name such as Typing_Extensions returns HTTP 200 directly, without a redirect, and info.name is typing-extensions.](json-api-accepts-unnormalized-name.md) · GET /pypi/{project}/json · env prod
- ✅ verified:server:prod · [JSON API responses are CDN-cached with Cache-Control max-age=900 and carry ETag and X-PyPI-Last-Serial.](json-api-cdn-cache.md) · GET /pypi/{project}/json · env prod
- ✅ verified:server:prod · [GET /pypi/{project}/json/ with a trailing slash returns HTTP 301 with a relative Location /pypi/{project}/json and an HTML body, not JSON.](json-trailing-slash-301.md) · GET /pypi/{project}/json/ · env prod
- 🔵 official · [JSON API metadata comes from the values given at upload time, not from the files, and the first upload of a release is stored: later uploads to that release do not update it.](release-metadata-from-first-upload.md) · GET /pypi/{project}/{version}/json · env prod
- ✅ verified:server:prod · [GET /simple/{project}/ returns HTML unless Accept asks for application/vnd.pypi.simple.v1+json; the JSON form has name, versions and meta.\_last-serial, and Vary lists Accept.](simple-api-html-unless-accept-json.md) · GET /simple/{project}/ · env prod
- ✅ verified:server:prod · [GET /simple/{project}/ with a non-normalized name such as Typing_Extensions returns HTTP 301 to the PEP 503 normalized URL /simple/typing-extensions/.](simple-unnormalized-name-301.md) · GET /simple/{project}/ · env prod
- ✅ verified:server:prod · [GET /simple/{project} without the trailing slash returns HTTP 301 to /simple/{project}/ instead of the project page.](simple-without-trailing-slash-301.md) · GET /simple/{project} · env prod

## Deprecations

- ✅ verified:server:prod · [info.downloads in the JSON API is deprecated: last_day, last_week and last_month are always -1, and bugtrack_url is always null.](downloads-always-minus-one.md) · GET /pypi/{project}/json · env prod
- 🔵 official · [The releases key of GET /pypi/{project}/json is deprecated and may be removed; projects should get release files from the Index API instead.](releases-key-deprecated.md) · GET /pypi/{project}/json · env prod
- 🔵 official · [The XML-RPC API is planned for deprecation and may be rate limited; no new integration should use it, and existing consumers should move to the JSON, RSS or Index APIs.](xml-rpc-planned-deprecation.md) · POST /pypi · env prod

## Schema drift

- ✅ verified:server:prod · [On 2026-10-20 /pypi/{project}/json had the top-level keys info, last_serial, ownership, releases, urls and vulnerabilities, schema fingerprint f2ea8b7e27a470cf.](project-json-fingerprint.md) · GET /pypi/{project}/json · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
