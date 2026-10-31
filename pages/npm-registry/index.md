# npm registry

Hosts: `registry.npmjs.org` · 5 facts

## Error meanings

- ✅ verified:server:prod · [`Not Found`](dist-tags-not-found-404.md) · GET /-/package/{package}/dist-tags · env prod
- ✅ verified:server:prod · [`Not Found`](missing-package-version-path-404.md) · GET /{package}/{version} · env prod
- ✅ verified:server:prod · [`Not found`](package-not-found-404.md) · GET /{package} · env prod
- ✅ verified:server:prod · [`'text' query parameter is required`](search-text-missing-400.md) · GET /-/v1/search · env prod
- ✅ verified:server:prod · [`version not found: 0.0.99`](version-not-found-404.md) · GET /{package}/{version} · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
