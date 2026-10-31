# Exceeding a rate limit or quota returns HTTP 429 RESOURCE_EXHAUSTED, a transient error, like 503 UNAVAILABLE; 400, 402 and 403 are client errors that a retry does not fix.

**Gemini API · POST /v1beta/models/{model_and_method} · HTTP 429 `RESOURCE_EXHAUSTED`**

Status: 🔵 official · first seen 2026-10-24

## What to do

1. Retry with exponential backoff from 1000 ms × 2, cap 60000 ms, ≤ 5 attempts, with jitter.

## In your code

When an SDK receives this response:

| SDK | Raises | Check |
| --- | --- | --- |
| Python `google-genai` | `google.genai.errors.ClientError` | `e.code == 429` · `e.status == "RESOURCE_EXHAUSTED"` |
| Node `@google/genai` | `ApiError` | `err.status === 429` |

Read from the SDK source: google-genai 2.34.0: google/genai/errors.py APIError.raise_error; @google/genai 2.32.0: dist/node/index.cjs throwErrorIfNotOK, class ApiError.

Fix 1:

```python
import random
import time

delay_ms = 1000
for attempt in range(5):
    response = client.send(request)
    if response.status_code != 429:
        break
    time.sleep(random.uniform(0, delay_ms) / 1000)
    delay_ms = min(delay_ms * 2, 60000)
```

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://ai.google.dev/gemini-api/docs/troubleshooting>

Observations: none from reporters yet.

## Related errors

- [`Your API key was reported as leaked. Please use another API key.`](leaked-key-403.md) · POST /v1beta/models/{model_and_method} · HTTP 403 `PERMISSION_DENIED`

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://generativelanguage.googleapis.com/v1beta/models/{model_and_method}"},"error":{"status":429}}'
```

YAML: [facts/google-gemini/resource-exhausted-429.yaml](../../facts/google-gemini/resource-exhausted-429.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
