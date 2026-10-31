# `Your API key was reported as leaked. Please use another API key.`

**Gemini API · POST /v1beta/models/{model_and_method} · HTTP 403 `PERMISSION_DENIED`**

Status: 🔵 official · first seen 2026-10-24

> A key that Google has detected as leaked is blocked: requests return HTTP 403 PERMISSION_DENIED "Your API key was reported as leaked. Please use another API key.".

## What to do

1. A human must enable new_api_key in the vendor dashboard (see https://ai.google.dev/gemini-api/docs/troubleshooting).

## In your code

When an SDK receives this response:

| SDK | Raises | Check |
| --- | --- | --- |
| Python `google-genai` | `google.genai.errors.ClientError` | `e.code == 403` · `e.status == "PERMISSION_DENIED"` |
| Node `@google/genai` | `ApiError` | `err.status === 403` |

Read from the SDK source: google-genai 2.34.0: google/genai/errors.py APIError.raise_error; @google/genai 2.32.0: dist/node/index.cjs throwErrorIfNotOK, class ApiError.

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://ai.google.dev/gemini-api/docs/troubleshooting>

Observations: none from reporters yet.

## Related errors

- [`Method doesn't allow unregistered callers (callers without established identity). Please use API Key or other form of API consumer identity to call this API.`](missing-api-key-403.md) · GET /v1beta/models · HTTP 403 `PERMISSION_DENIED`
- [Exceeding a rate limit or quota returns HTTP 429 RESOURCE_EXHAUSTED, a transient error, like 503 UNAVAILABLE; 400, 402 and 403 are client errors that a retry does not fix.](resource-exhausted-429.md) · POST /v1beta/models/{model_and_method} · HTTP 429 `RESOURCE_EXHAUSTED`

## Machine access

Match signature (what `check()` matches): `your api key was reported as leaked. please use another api key.`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://generativelanguage.googleapis.com/v1beta/models/{model_and_method}"},"error":{"status":403,"body_excerpt":"your api key was reported as leaked. please use another api key."}}'
```

YAML: [facts/google-gemini/leaked-key-403.yaml](../../facts/google-gemini/leaked-key-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
