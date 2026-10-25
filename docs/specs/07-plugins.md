# 07 · Test-runner plugins and MCP

**Done when (wave 1):** `pip install apifacts-pytest` + `-p apifacts` makes a failing test whose
exception is an HTTP error (`requests.HTTPError`, `httpx.HTTPStatusError`, or an SDK error carrying
`status_code`/`http_status` and `request.url`) print a "Known facts" section in the failure report,
sourced from `POST /v0/check`; nothing is sent when the host is not in the registry's `GET /v0/services`
cache; opt-out `APIFACTS_DISABLE=1`; all of this covered by tests against a local fake server.

## pytest plugin (`plugins/pytest/`, package `apifacts-pytest`)

- Hook: `pytest_runtest_makereport` on failure → walk the exception chain → extract `(method, url,
  status, body_excerpt ≤ 2 KB)` → if host ∈ cached service hosts → `check()` with 2 s timeout →
  append section:

```
──────────── Known facts (apifacts, CC BY 4.0) ────────────
POST api.stripe.com/v1/payment_intents → 400 idempotency_error
✅ verified:server:sandbox · Reusing an Idempotency-Key with a different request body returns HTTP 400 …
   fix: Send header Idempotency-Key = new UUID per distinct request
   https://apifacts.dev/stripe/idempotency-key-reuse-different-params
```

- Privacy: never sends request bodies, headers, query strings or tokens; strips the secret-shaped
  patterns from `body_excerpt` client-side; one request per failure, none on pass.
- Config: `APIFACTS_ENDPOINT` (default `https://apifacts.dev`), `APIFACTS_DISABLE`,
  `--apifacts-offline` (use the cached YAML snapshot shipped in the wheel, no network).
- Cache: `GET /v0/services` hosts list (`hosts` + `instance_hosts`) cached 24 h in `~/.cache/apifacts/`.
  A tenant host such as `<org>.my.salesforce.com` is sent under its registry host (`my.salesforce.com`):
  the org name does not leave the machine; the offline snapshot matches the same way (D-090).

## jest plugin (wave 2, `plugins/jest/`, package `@apifacts/jest`)

Same behaviour via a custom reporter: on test failure inspect `error.response` (axios), `error.status`
+ `error.request` (fetch wrappers, SDKs); same privacy rules; TypeScript, vitest-compatible reporter too.

## MCP server (wave 2, `apifacts/mcp`)

One tool only: `check(target, error?)` with a 40-word description; no resources, no prompts. Listed in
the official registry after pages and plugins exist (plan §21: pages and plugins before MCP).

Shipped as `apifacts mcp` (`apifacts/mcp_server.py`, stdio) behind the extra `apifacts[mcp]`, so the
plugin's users do not pull the MCP SDK: `uvx --from 'apifacts[mcp]' apifacts mcp`. The error is passed
flat — `check(target, method?, status?, body?)` — because clients fill flat arguments more reliably
than a nested object; `body` may arrive as a JSON object (the SDK parses JSON strings) and is
re-serialized. Same client as the CLI (filters, 2 s timeout, 20 checks per session, `APIFACTS_DISABLE`,
`--offline` from the packaged snapshot); every failure is a text answer starting with `error:`.
`server.json` at the repository root is the registry entry (`io.github.illouminus/apifacts`, PyPI,
`runtimeHint: uvx`); README.en.md carries the `mcp-name:` line the registry looks for on PyPI.

## CLI (wave 1, part of `apifacts`)

`apifacts check <url-or-locator> [--status N --body file]` for humans and shell agents; prints the
same section as the plugin.
