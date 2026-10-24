# 07 · Test-runner plugins and MCP

**Done when (wave 1):** `pip install agentfacts-pytest` + `-p agentfacts` makes a failing test whose
exception is an HTTP error (`requests.HTTPError`, `httpx.HTTPStatusError`, or an SDK error carrying
`status_code`/`http_status` and `request.url`) print a "Known facts" section in the failure report,
sourced from `POST /v0/check`; nothing is sent when the host is not in the registry's `GET /v0/services`
cache; opt-out `AGENTFACTS_DISABLE=1`; all of this covered by tests against a local fake server.

## pytest plugin (`plugins/pytest/`, package `agentfacts-pytest`)

- Hook: `pytest_runtest_makereport` on failure → walk the exception chain → extract `(method, url,
  status, body_excerpt ≤ 2 KB)` → if host ∈ cached service hosts → `check()` with 2 s timeout →
  append section:

```
──────────── Known facts (agent-facts, CC BY 4.0) ────────────
POST api.stripe.com/v1/payment_intents → 400 idempotency_error
✅ verified:server:sandbox · Reusing an Idempotency-Key with a different request body returns HTTP 400 …
   fix: Send header Idempotency-Key = new UUID per distinct request
   https://github.com/Illouminus/agent-facts/blob/main/pages/stripe/idempotency-key-reuse-different-params.md
```

- Privacy: never sends request bodies, headers, query strings or tokens; strips the secret-shaped
  patterns from `body_excerpt` client-side; one request per failure, none on pass.
- Config: `AGENTFACTS_ENDPOINT` (default `https://facts.baillot.dev`), `AGENTFACTS_DISABLE`,
  `--agentfacts-offline` (use the cached YAML snapshot shipped in the wheel, no network).
- Cache: `GET /v0/services` hosts list (`hosts` + `instance_hosts`) cached 24 h in `~/.cache/agentfacts/`.
  A tenant host such as `<org>.my.salesforce.com` is sent under its registry host (`my.salesforce.com`):
  the org name does not leave the machine; the offline snapshot matches the same way (D-090).

## jest plugin (wave 2, `plugins/jest/`, package `@agent-facts/jest`)

Same behaviour via a custom reporter: on test failure inspect `error.response` (axios), `error.status`
+ `error.request` (fetch wrappers, SDKs); same privacy rules; TypeScript, vitest-compatible reporter too.

## MCP server (wave 2, `agentfacts/mcp`)

One tool only: `check(target, error?)` with a 40-word description; no resources, no prompts. Listed in
the official registry after pages and plugins exist (plan §21: pages and plugins before MCP).

## CLI (wave 1, part of `agentfacts`)

`agentfacts check <url-or-locator> [--status N --body file]` for humans and shell agents; prints the
same section as the plugin.
