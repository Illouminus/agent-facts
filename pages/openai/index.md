# OpenAI API

Hosts: `api.openai.com` · 5 facts

## Silent behavior

- ✅ verified:server:prod · [Errors are a JSON object {error: {message, type, param, code}}; code can be null (a missing key), so the vendor code is error.code when set, else error.type, and the request id comes only in the x-request-id header.](error-envelope.md) · GET /v1/models · env prod

## Auth quirks

- ✅ verified:server:prod · [`Incorrect API key provided: apifacts********-key. You can find your API key at https://platform.openai.com/account/api-keys.`](invalid-api-key-401.md) · GET /v1/models · env prod
- ✅ verified:server:prod · [`Incorrect API key provided: apifacts********-key. You can find your API key at https://platform.openai.com/account/api-keys.`](invalid-api-key-before-model-lookup.md) · GET /v1/models/{model} · env prod
- ✅ verified:server:prod · [`Missing bearer authentication in header`](missing-api-key-401.md) · GET /v1/models · env prod
- ✅ verified:server:prod · [`Missing bearer authentication in header`](missing-api-key-before-model-lookup.md) · GET /v1/models/{model} · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
