# apifacts-pytest

A pytest plugin for the [apifacts](https://github.com/Illouminus/apifacts) registry: when a test
fails on an HTTP error from a registered API, the failure report gets a section with the verified facts
about that error and their typed fixes. Zero tokens and zero requests until a test fails.

```
pip install apifacts-pytest      # loads automatically; or: pytest -p apifacts
```

```
──────────── Known facts (apifacts, CC BY 4.0) ────────────
POST api.stripe.com/v1/payment_intents → 400 idempotency_error
✅ verified:server:prod · Reusing an Idempotency-Key with a different request body returns HTTP 400 …
   fix: Send header Idempotency-Key = new UUID per distinct request
   https://apifacts.dev/stripe/idempotency-key-reuse-different-params
```

## What it reads and sends

- Recognized exceptions anywhere in the chain (`__cause__`, `__context__`, exception groups):
  `requests.HTTPError`, `httpx.HTTPStatusError`, and SDK errors carrying `status_code`/`http_status`
  and `request.url` (OpenAI, Anthropic and similar clients).
- Nothing is sent unless the host is in the registry's service list (`GET /v0/services`, cached 24 h
  in `~/.cache/apifacts/`). Then one `POST /v0/check` per distinct failure, 2 s timeout, at most 20
  per session; none on a pass; the first network failure turns the plugin off for the session.
- Sent: method, `scheme://host/path` (no query, fragment, credentials or port; secret-looking path
  segments and tenant subdomains replaced), status, the first 2 KB of the error body with secrets,
  e-mail addresses, long ids and URL query strings removed, and the vendor SDK name and version.
  Never sent: request bodies, headers, cookies, tokens.
- Any plugin error is swallowed: it never changes a test outcome.

## Configuration

| Setting | Effect |
|---------|--------|
| `APIFACTS_DISABLE=1` or `-p no:apifacts` | off |
| `APIFACTS_ENDPOINT` | registry URL (default `https://apifacts.dev`) |
| `--apifacts-offline` | no network: answer from the snapshot shipped in the package |
| `APIFACTS_SNAPSHOT=<dir>` | snapshot directory (`services/*.yaml`, `facts/*/*.yaml`) for offline mode |

Code MIT; facts CC BY 4.0.
