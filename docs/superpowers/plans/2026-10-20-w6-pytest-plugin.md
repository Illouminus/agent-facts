# W6 · pytest plugin + CLI `check` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a failing test whose exception is an HTTP error prints a "Known facts (agent-facts, CC BY 4.0)"
section sourced from `POST /v0/check` (spec 07, wave 1), and `agentfacts check <url-or-locator>` prints
the same section for humans and shell agents.

**Architecture:** the client side of `check()` lives once in the main package, `agentfacts/client/`
(stdlib-only at import time: `urllib`, `json`, `re`): building a privacy-safe request (URL scrub,
secret redaction, 2 KB excerpt), the transport (services cache, one bounded POST, circuit breaker,
offline snapshot) and the text rendering. The plugin (`plugins/pytest/`, package `agentfacts-pytest`,
depends on `agentfacts`) adds only what is pytest-specific: walking the exception chain, configuring the
client from env/options, attaching the section to the report. The CLI (`agentfacts/cli_check.py`) builds
the same request from its arguments and prints the same section.

**Tech Stack:** Python 3.12, pytest ≥ 8 (`wrapper=True` hooks, `pytester`), stdlib `urllib.request`,
typer, pytest-httpserver (fake `check()` server), requests + httpx (real exception types in tests), uv.

**Spec:** `docs/specs/07-plugins.md` (wave 1), `docs/specs/03-check-contract.md`, `docs/specs/09-work-breakdown.md` § W6.

---

## Decisions (recorded in the PR)

| Question | Decision | Why |
|----------|----------|-----|
| Where the shared code lives | `agentfacts/client/{request,transport,render,offline,settings}.py`; plugin depends on `agentfacts` | CLI and plugin import one implementation; the MCP server (W9) can reuse it |
| HTTP library for the client | stdlib `urllib.request`, not httpx/requests | the user's tests often mock httpx/requests (`pytest-httpx`, `respx`, `responses`); the hook runs while those mocks are still active, so a call through them would be intercepted or recorded |
| Where the section goes | `report.longrepr.addsection(title, body, sep="─")`, fallback `report.sections` | right after the traceback, not filtered by `--show-capture`, survives xdist serialization and junitxml |
| Fix sentences | rendered client-side from the typed `fixes` with `agentfacts.fixes.templates.render_fix`; server `fixes_rendered[i]` only when the client does not know the action | keeps the closed-vocabulary guarantee even against a misbehaving endpoint |
| Facts empty | plugin prints nothing; CLI prints `no known facts (<reason>)` | no noise in failure reports |
| Tenant subdomains (`acme.my.salesforce.com`) | gate on exact-or-subdomain match, then send the registered host instead of the tenant host | the tenant name identifies the user |
| Request bounds per session | memo of identical requests, ≤ 20 checks, ≤ 10 s spent on network, breaker on the first failure | a red suite of 500 tests must not get 500 × 2 s slower |
| Local hosts | `localhost`, IPs, single-label and `.local/.test/.internal/.localhost/.example/.invalid` never trigger the services fetch | test servers fail a lot; no point asking the registry |
| Offline snapshot | `agentfacts/client/snapshot/` (empty in wave 1; `services/*.yaml`, `facts/*/*.yaml` layout), override `AGENTFACTS_SNAPSHOT=<dir>` | the mechanism exists and is tested; W8 fills it at release |
| Test env | plugin is its own uv project (`plugins/pytest/uv.lock`, `agentfacts` as editable path source) | the root suite does not load the plugin; no change to the root `pyproject.toml`/`uv.lock` (shared with W2/W3/W5) |

## File map

| File | Responsibility |
|------|----------------|
| `agentfacts/client/__init__.py` | package docstring: "client side of check()" |
| `agentfacts/client/request.py` | `redact(text)`, `excerpt(text)` (redact then cut to 2048 UTF-8 bytes), `scrub_url(url)`, `Signal` (url, method, status, body_excerpt, sdk) with `.host`, `.with_host(h)`, `.payload()`; `make_signal(...)` |
| `agentfacts/client/settings.py` | `Settings(endpoint, disabled, snapshot)` from env: `AGENTFACTS_ENDPOINT`, `AGENTFACTS_DISABLE`, `AGENTFACTS_SNAPSHOT`; `DEFAULT_ENDPOINT` |
| `agentfacts/client/transport.py` | `Client(endpoint, user_agent, *, timeout=2.0, cache_dir, offline, snapshot, ...)`: `registered_host(host)`, `check(payload)`, `last_error` |
| `agentfacts/client/offline.py` | `Snapshot.load(root)`, `.hosts`, `.check(payload)` → same shape as the server response |
| `agentfacts/client/snapshot/README.md` | marks the packaged (empty) snapshot directory |
| `agentfacts/client/render.py` | `TITLE`, `render_section(result, signal, *, show_empty=False)`, `title_line(width)` |
| `agentfacts/cli_check.py` | `check` command: `<url-or-locator> [--method/-X] [--status N] [--body FILE] [--offline] [--json]` |
| `agentfacts/cli.py` | one import + `app.command("check")(check)` |
| `plugins/pytest/pyproject.toml` | `agentfacts-pytest`, entry point `pytest11: agentfacts = agentfacts_pytest.plugin` |
| `plugins/pytest/README.md` | install, what is sent, opt-out, config |
| `plugins/pytest/agentfacts_pytest/__init__.py` | `__version__` |
| `plugins/pytest/agentfacts_pytest/extract.py` | `iter_chain(exc)`, `signal_from_exception(exc)`, `sdk_context(exc)` |
| `plugins/pytest/agentfacts_pytest/client.py` | `make_client(config)`: settings + `--agentfacts-offline` + user agent `agentfacts-pytest/<v>` |
| `plugins/pytest/agentfacts_pytest/render.py` | `attach(report, title, body)` |
| `plugins/pytest/agentfacts_pytest/plugin.py` | `pytest_addoption`, `pytest_configure`, `pytest_runtest_makereport` |
| `tests/client/test_{request,transport,render,offline}.py`, `tests/test_cli_check.py` | main package |
| `plugins/pytest/tests/{conftest,test_extract,test_plugin}.py` | plugin (pytester + pytest-httpserver) |
| `.github/workflows/ci.yml` | two steps in the same job: `uv sync --locked` + `uv run pytest -q` in `plugins/pytest` |

## Request built by the client (spec 03)

```json
{"target": {"method": "POST", "url": "https://api.stripe.com/v1/payment_intents"},
 "error": {"status": 400, "body_excerpt": "<redacted, ≤ 2048 bytes>"},
 "context": {"sdk": {"package": "openai", "ecosystem": "pypi", "version": "2.3.0"}}}
```

Only these keys; `method`, `error`, `context` omitted when unknown. URL = `scheme://host/path`: query,
fragment, userinfo and port dropped; path segments that look like secrets (a `[A-Za-z0-9_-]` run ≥ 24
holding a letter and a digit, or a known token shape) become `<redacted>` (template slots match them).
User-Agent `agentfacts-pytest/0.1.0 (+https://github.com/Illouminus/agent-facts)` / `agentfacts-cli/0.1.0 (…)`.

## Redaction (client-side, before truncation)

| Pattern | Replacement |
|---------|-------------|
| PEM private key block | `<redacted>` |
| query string / fragment of any URL in the text | dropped |
| `Bearer|Basic|Token <value ≥ 8>` | `Bearer <redacted>` |
| `api_key|token|secret|password|…` followed by `:`/`=` and a value | name kept, value `<redacted>` |
| known shapes: `sk_/pk_/rk_live|test_…`, `whsec_…`, `…_secret_…`, `gh[pousr]_…`, `github_pat_…`, `xox?-…`, `sk-…`, `AIza…`, `AKIA/ASIA…`, JWT, Telegram bot token, `SG.…`, `glpat-…`, `hf_…`, `npm_…` | `<redacted>` |
| e-mail address | `<email>` |
| `[A-Za-z0-9+/_=-]` run ≥ 32: pure hex/UUID | `<id>` (the server normalizes hex the same way) |
| same run with a letter and a digit | `<redacted>` |

Input is capped at 16 KB before redaction, output at 2048 bytes after (no split UTF-8 character); a
secret that starts inside the first 2 KB is always seen whole by the patterns.

## Section format (spec 07)

```
──────────── Known facts (agent-facts, CC BY 4.0) ────────────
POST api.stripe.com/v1/payment_intents → 400 idempotency_error
✅ verified:server:prod · Reusing an Idempotency-Key with a different request body returns HTTP 400 …
   fix: Send header Idempotency-Key = new UUID per distinct request
   https://github.com/Illouminus/agent-facts/blob/main/pages/stripe/idempotency-key-reuse-different-params.md
```

Target line: method, host + matched template path (else the scrubbed path), `→ status`, the error code of
the first fact with that status. Badges: ✅ verified:*, 📘 official, 🟡 reported, ⚪ stale, ✖ retracted,
• anything else. ≤ 5 facts, then `… N more facts`. Every server string is stripped of control characters
and collapsed to one line; page URL only when `id` matches `af:<service>:<slug>`.

---

### Task 1: request building and redaction (TDD)

**Files:** Create `agentfacts/client/__init__.py`, `agentfacts/client/request.py`; Test `tests/client/test_request.py`.

- [ ] **Step 1: failing tests** — `redact`: each known shape → `<redacted>` (parametrized), `Bearer x…`,
  `"api_key": "…"` keeps the name, e-mail → `<email>`, 40-hex and UUID → `<id>`, mixed 40-char run →
  `<redacted>`, URL query dropped, Stripe's real idempotency message unchanged; `excerpt`: ≤ 2048 bytes,
  multi-byte char not split, a secret starting at byte 2040 never leaks a prefix; `scrub_url`: drops
  query/fragment/userinfo/port, redacts token-like path segments (Telegram `bot<id>:<token>`, Slack
  webhook secret), keeps `/v1/payment_intents` and `gemini-2.5-pro:generateContent`, non-http → None;
  `make_signal` + `payload()` → exactly the spec 03 keys, `None`s omitted; `with_host`.
- [ ] **Step 2:** `uv run pytest -q tests/client/test_request.py` → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: implement** per the redaction table; linear regexes only (token runs judged by a
  callback, no look-ahead scans) so a 16 KB body costs microseconds.
- [ ] **Step 4:** run → PASS; `uv run ruff check .`; commit `feat(w6): client-side check() request with redaction`.

### Task 2: settings, transport, offline snapshot (TDD)

**Files:** Create `agentfacts/client/settings.py`, `agentfacts/client/transport.py`,
`agentfacts/client/offline.py`, `agentfacts/client/snapshot/README.md`; Test `tests/client/test_transport.py`, `tests/client/test_offline.py`.

- [ ] **Step 1: failing tests** (pytest-httpserver, `cache_dir=tmp_path`, injected clock):
  services fetched once and cached (`services.json` with endpoint + time + hosts); cache hit → no
  request; cache older than 24 h or for another endpoint → refetch; unreachable endpoint → empty and
  silent; `registered_host` exact, subdomain → registered host, local hosts never fetch; `check` posts
  JSON with the UA and content type and returns the dict; 500, invalid JSON, non-object, oversize
  body, timeout (`timeout=0.2` vs a 0.5 s handler), redirect → `None` and breaker open (next call sends
  nothing); identical payload → one request; `max_checks` cap; offline client → no request at all.
  Offline: snapshot from `tests/fixtures/valid` → stripe fact for `POST /v1/payment_intents` 400 with
  `fixes_rendered`; unknown host → `unregistered_target`; packaged snapshot is empty; settings parse
  `AGENTFACTS_DISABLE` truthy values and default endpoint.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement** `Client` with `urllib.request` opener without redirect handling; every
  failure sets `last_error` and the breaker; cache written atomically (`tmp` + `os.replace`), write
  errors ignored. `Snapshot` loads YAML with `yaml.safe_load`, matches host, template
  (`agentfacts.schema.registry.match_template`), then facts by `(template, status)` else
  `kind ∈ {rate_limit, availability}`; retracted facts never returned.
- [ ] **Step 4:** run → PASS; commit `feat(w6): check() transport with services cache and offline snapshot`.

### Task 3: rendering (TDD)

**Files:** Create `agentfacts/client/render.py`; Test `tests/client/test_render.py`.

- [ ] **Step 1: failing tests** — golden: the spec 07 example (fact with `set_header` fix) renders the
  exact four body lines; `fixes_rendered` used only for an unknown action; control characters stripped;
  > 5 facts → `… 2 more facts`; bad `id` → no URL line; empty facts → `None`, and with `show_empty` →
  target line + `no known facts (unregistered_target)`; `title_line(64)` is 64 wide.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** PASS; commit `feat(w6): Known facts section rendering`.

### Task 4: pytest plugin (TDD)

**Files:** Create everything under `plugins/pytest/`; Test `plugins/pytest/tests/test_extract.py`, `plugins/pytest/tests/test_plugin.py`.

- [ ] **Step 1: project** — `pyproject.toml` (hatchling, deps `agentfacts>=0.1.0`, `pytest>=8`; dev
  `pytest-httpserver`, `requests`; `[tool.uv.sources] agentfacts = {path = "../..", editable = true}`;
  pytest `addopts = ["-p", "no:agentfacts"]` so the outer run is hermetic); `cd plugins/pytest && uv lock && uv sync`.
- [ ] **Step 2: failing extract tests** — `requests.HTTPError` from `raise_for_status()` on a built
  `Response` (method, scrubbed url, status, body); `httpx.HTTPStatusError`; SDK-like object with
  `status_code` + `request.url`; object with `http_status` + `request.url`; `__cause__`, `__context__`,
  `ExceptionGroup`; cycles terminate; no URL / bool or out-of-range status / raising property → `None`;
  unread httpx stream and unread requests stream → no read, body from `str(exc)`; `sdk_context` for a
  class whose module belongs to an installed distribution, none for requests/httpx/test modules.
- [ ] **Step 3: failing pytester tests** (fake `check()` on pytest-httpserver; `AGENTFACTS_ENDPOINT`,
  `XDG_CACHE_HOME` monkeypatched): section printed for a stripe 400 (fnmatch on the five lines); posted
  JSON has no query, header, body secret, only spec keys; UA `agentfacts-pytest/`; passing test → zero
  requests; host not in registry → only `GET /v0/services`, no POST; `AGENTFACTS_DISABLE=1` → zero
  requests; `/v0/check` 500, garbage, closed port → `1 failed`, no `INTERNALERROR`, no section; same
  error twice → one POST; setup-phase HTTP error annotated too; `--agentfacts-offline` +
  `AGENTFACTS_SNAPSHOT` → section with zero requests; subprocess run with
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 -p agentfacts` loads the entry point.
- [ ] **Step 4:** `cd plugins/pytest && uv run pytest -q` → FAIL.
- [ ] **Step 5: implement** `extract.py`, `client.py`, `render.py`, `plugin.py` (state in
  `config.stash`, every plugin step inside `try/except Exception`).
- [ ] **Step 6:** PASS; commit `feat(w6): agentfacts-pytest plugin`.

### Task 5: CLI `agentfacts check` (TDD)

**Files:** Create `agentfacts/cli_check.py`; Modify `agentfacts/cli.py` (one import, one registration); Test `tests/test_cli_check.py`.

- [ ] **Step 1: failing tests** (CliRunner + httpserver): URL + `-X POST --status 400 --body FILE` →
  section on stdout, posted body redacted; `--json` → the raw response; locator `pypi:stripe@12.1.0`
  and bare host sent verbatim; not a URL/host/locator → exit 2; missing body file → exit 2; unreachable
  → exit 1 with `error:` on stderr; no facts → `no known facts (…)`, exit 0; `--offline` with
  `AGENTFACTS_SNAPSHOT`; `check` listed in `agentfacts --help`.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS; commit `feat(w6): agentfacts check CLI`.

### Task 6: CI, docs, PR

- [ ] `.github/workflows/ci.yml`: after the root `pytest` step, `uv sync --locked` and `uv run pytest -q`
  with `working-directory: plugins/pytest`.
- [ ] `uv run ruff check .`, `uv run pytest -q`, `cd plugins/pytest && uv run pytest -q`,
  `uv build --package`-free check: `cd plugins/pytest && uv build` and the wheel lists the entry point.
- [ ] Rebase on `origin/main`, push, PR ready with "Assumptions that might be wrong", `/code-review`,
  fix every finding in the same PR, CI green, squash-merge, remove the worktree, state journal line.
