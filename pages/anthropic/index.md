# Claude API (Anthropic)

Hosts: `api.anthropic.com` · 5 facts

## Silent behavior

- ✅ verified:server:prod · [Errors are a JSON object {type: "error", error: {type, message}, request_id}; the vendor code is error.type (e.g. authentication_error) and the request id also comes in the request-id header.](error-envelope.md) · GET /v1/models · env prod

## Auth quirks

- ✅ verified:server:prod · [`invalid x-api-key`](invalid-api-key-401.md) · GET /v1/models · env prod
- ✅ verified:server:prod · [`invalid x-api-key`](invalid-api-key-before-model-lookup.md) · GET /v1/models/{model_id} · env prod
- ✅ verified:server:prod · [`x-api-key header is required`](missing-api-key-401.md) · GET /v1/models · env prod
- ✅ verified:server:prod · [`x-api-key header is required`](missing-api-key-before-model-lookup.md) · GET /v1/models/{model_id} · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
