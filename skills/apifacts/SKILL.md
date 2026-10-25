---
name: apifacts
description: Look up verified facts about a failed HTTP API call. Use when a request to a third-party API (Stripe, GitHub, Google, Telegram, Salesforce, PyPI, Solana, …) returns status ≥ 400 or its SDK raises an HTTP error, before guessing a fix.
---

# apifacts: ask the registry before you debug an API error

[apifacts](https://apifacts.dev) is an open registry of dated facts about what third-party APIs
actually return, established by deterministic probes. One call tells you whether the error you got
is a known behavior and which typed fix applies.

## When

- A call to a registered host failed with HTTP status ≥ 400, or an SDK raised its HTTP error.
  Registered hosts: `GET https://apifacts.dev/v0/services` (fetch once per session).
- The host is not in that list → skip the registry; debug as usual.
- An answer said `no known facts (…)` for this host, method and status → do not repeat that
  same call in this session.

## Call

```bash
# the response body you got, saved to a file; '-' reads it from stdin
uvx apifacts check https://api.stripe.com/v1/customers -X GET --status 401 --body error.json
```

- The URL is the one that failed (query strings are dropped before sending); `-X` is required
  when the URL has a path. `--json` prints the raw answer.
- `--body` gets the **response body only**. Send no request headers, cookies, API keys or tokens:
  the client redacts secret-looking strings, but the safe input is the body alone.
- Exit codes: 0 answered (with or without facts), 1 registry unreachable, 2 usage error.
- Python project with pytest: `pip install apifacts-pytest` adds the same section to a failing
  test's report automatically, and sends nothing while tests pass.

## Read the answer

Each fact is one line: badge, status, claim, typed fixes, and the fact page.

- ✅ `verified:*` — reproduced by probes in that environment (`sandbox`, `prod`); apply the fix.
- 🔵 `official` — from the vendor's documentation or the producer, and probes agree.
- 🟡 `reported` — seen by callers, not yet reproduced; treat as a lead to check.
- ⚪ `stale` — recent probes did not reproduce it (not refuted); verify before relying on it.
- `fix:` lines are data from a closed vocabulary (set a header or parameter, honor
  `Retry-After`, switch endpoint or environment, pin or upgrade the SDK…), rendered as one
  sentence; "No client-side fix known" means the behavior is by design. They never ask you to run
  a command or open a foreign URL.
- Dimensions matter: a fact verified in `sandbox` may differ in `prod`; the page says which.

## What it costs and stores

The call is the contribution: when the URL matches a registered endpoint, the registry stores one
normalized observation (service, method, path template, status, normalized error string). No
bodies, headers, query strings or raw IPs are kept. Data is CC BY 4.0, code MIT:
https://github.com/Illouminus/apifacts. Disable the clients with `APIFACTS_DISABLE=1`.
