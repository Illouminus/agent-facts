# W2 · Probe runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `apifacts probe run [--due|--all] [--max N] [--max-requests N] [--vantage NAME] [--dry-run]`
executes declarative probes (`probes/<service>/*.yaml`), writes one redacted JSON line per run to
`results.jsonl`, confirms or demotes the facts that cite the probe, respects budgets and the kill switch,
and injects keys only by name; `apifacts probe list` shows what is due.

**Architecture:** One tick = kill check → load + validate the registry (W1 `validate_paths`, then the
pydantic models) → select due probes (sqlite budget state, oldest first, capped) → read the keys of the
selected keyed services → per probe: render templates, re-check the rendered request (template instance,
prod read-only, auth env), send with httpx, evaluate assertions → apply the outcome to facts (ruamel
round-trip, re-validated as `Fact` before writing) → append the redacted record → update budget state.
No LLM anywhere; no code per probe.

**Tech Stack:** Python 3.12, httpx 0.28 (sync client, no redirects), pydantic models from
`apifacts.schema.models`, ruamel.yaml round-trip, stdlib `sqlite3`, typer; tests with
`pytest-httpserver` (already a dev dependency) — no real network.

**Spec:** `docs/specs/04-probe-runner.md`, `docs/specs/01-fact-schema.md` (probe, service, fact, status
rules), `docs/specs/00-architecture.md` invariants 1, 4, 5, 6, `docs/specs/09-work-breakdown.md` § W2.

---

## File map

| File | Responsibility |
|------|----------------|
| `apifacts/probe/__init__.py` | package doc; `USER_AGENT` |
| `apifacts/probe/loader.py` | `load_repo(root) -> Repo(services, probes, facts, problems)`: `validate_paths` gate, then `Service`/`Probe`/`Fact` models; files with problems are skipped and reported |
| `apifacts/probe/templating.py` | `RunContext(run_uuid, now_rfc3339, responses)`, `render(value, ctx)`, `render_path(path, ctx)`, `lookup(doc, path)`; only `{{run_uuid}}`, `{{now_rfc3339}}`, `{{step[N].json.<path>}}` |
| `apifacts/probe/http.py` | `PreparedRequest`, `prepare(step, ctx, service, env)` (render + re-check), `auth_for(service, key)`, `send(client, base_url, request) -> StepResponse` (timeout, UA, body cap) |
| `apifacts/probe/assertions.py` | `evaluate(assertion, responses) -> AssertResult`; `schema_fingerprint(body_json)` |
| `apifacts/probe/budget.py` | `BudgetState(path)` sqlite: last run per (probe, vantage) and per (service, method, template, vantage); `is_due`, `record` |
| `apifacts/probe/keys.py` | `DEFAULT_KEYS_DIR`, `has_key`, `read_key` (`<dir>/<key_name>.key`, stripped; empty = missing) |
| `apifacts/probe/redact.py` | `Redactor(secrets)`: exact values, `sk_[a-z]+_[A-Za-z0-9]{8,}`, `Bearer [A-Za-z0-9._-]{16,}`, hex ≥ 32, base64 ≥ 32 (with a digit and a letter); `redact_record` |
| `apifacts/probe/evidence.py` | `apply_outcome(fact_path, outcome, probe, vantage, now) -> change`; ruamel round-trip that keeps comments, quotes and timestamps byte-identical |
| `apifacts/probe/results.py` | `ResultsLog(path, redactor).append(record)`: redacted JSON line |
| `apifacts/probe/runner.py` | `TickOptions`, `run_tick(...) -> TickReport`; `killed(root)`; `execute(probe, ...)` |
| `apifacts/probe/cli.py` | typer sub-app `probe` with `run` and `list` |
| `apifacts/cli.py` | `app.add_typer(probe_app, name="probe")` (+ its import) |
| `.gitignore` | `var/` (default state dir: results + sqlite) |
| `tests/probe/conftest.py` | `repo` fixture: writes a service/probes/facts tree into `tmp_path`; fake keys dir |
| `tests/probe/test_*.py` | one file per module + `test_runner.py` (end-to-end against `httpserver`) + `test_cli.py` |
| `tests/fixtures/probe-repo/{services,probes,facts}/…` | the dry-run fixture (one keyless prod service, one keyed sandbox service) |

## Decisions (go into the PR "Assumptions" section)

- **State = sqlite** `<state-dir>/probe-state.sqlite` next to `<state-dir>/results.jsonl`; default
  `--state-dir` is `<root>/var` (gitignored). sqlite because two overlapping ticks must not lose an update
  (00: sqlite holds transient state; losing it loses nothing verified).
- **Budget at two levels:** a probe is due when its own last run *and* the last run of every template it
  hits (per vantage) are ≥ `per_template_seconds` ago — invariant 6 is per endpoint template, and two
  probes on one template must not double the rate. `--all` skips the due check only; `--max`
  (probes, default 50) and `--max-requests` (http steps, default 50, spec design parameter) still cap
  the tick. Due probes run oldest-first (never-run first), ties by id.
- **One line per run** in `results.jsonl` (the task's wording and 04's record shape; 04's "Done when"
  says "per step" — the steps are inside the line).
- **Outcomes:** `pass` (every assertion ok), `fail` (≥ 1 assertion failed), `error` (transport error,
  unexpected 429, template error, refused request) and `skipped:no_key`. Only `pass`/`fail` touch facts:
  a timeout or our own rate limit is not evidence. Every outcome updates `last_run` (back-off).
- **Facts:** pass → `last_confirmed`, `confirmations += 1`, `stale_counter = 0`, vantage added; a `stale`
  fact is restored to the `previous_status` of its last `stale` history entry. Fail → `stale_counter += 1`;
  at ≥ 3 a `verified:*` fact becomes `stale` with `{change: stale, previous_status}` in history.
  `official`/`reported`/`retracted` statuses are never changed by the runner (01: their demotion rules are
  not probe-based; promotion `reported → verified` is W4's). Different `env` or `account_state`
  (probe `account_state` absent = `any`) → fact untouched, recorded as `other_dimension`.
- **Auth:** `bearer` → `Authorization: Bearer <key>`; `basic` → key file holds `user:password` (a key
  without `:` is the user with an empty password); `header` → `<header_name>: <key>`; `query` →
  `<param_name>=<key>` (the URL is never recorded). Base URL = `dimensions.env[probe.env]`, must be on the
  service's `hosts`; redirects are not followed (a key never follows a `Location`).
- **Runtime re-checks** (defence in depth after templating): rendered path is an instance of a registered
  template for the method, placeholders in a path are percent-encoded per segment (`/` → `%2F`, which
  `match_template` rejects), `http_step_violations(rendered, env)` (prod read-only, forbidden headers),
  keyed step with `probe.env != auth.env` refused. The runner's `User-Agent` always wins.
- **Fingerprint:** `schema_fingerprint` = sha256 of `json.dumps(sorted(top_level_keys), separators=(",",
  ":"))`; each step record carries it as `body_fingerprint` (null if the body is not a JSON object) so a
  probe author copies it from `results.jsonl`.
- **Redaction:** identifiers we generate (probe/fact ids, outcome, vantage, `body_fingerprint`) are exempt
  from the generic hex/base64 rule (they would otherwise be eaten); every field still goes through the exact
  key values, `sk_…` and `Bearer …`, and the final JSON line is scanned again.
- **Opt-out address** in the User-Agent: `edouard@baillot.dev` (the agents' mailbox, D-075).
- **Exit codes:** 0 tick done (assertion failures are data), 1 invalid/refused probes in the tick, 2 usage.
  Kill switch → exit 0 with `kill switch on (…): no requests` on stderr.

Added during implementation (automated security review of each commit, then `/code-review` of the
whole diff): redaction exemptions name full record paths (not key names at any depth); derived key
forms (URL-encoded, base64 `user:key`) and case-insensitive exact matching; vendor text redacted
*before* it is clipped or lowercased, details clipped after redaction; path placeholders may not render
empty, `.` or `..`; the body is decoded by the runner under the cap (identity asked, gzip/deflate
bounded, stop at stream end, 4 MiB raw cap, total deadline); header values must be ASCII without line
breaks (`invalid_header`); an unexpected 5xx is `error` like an unexpected 429 (an outage is not a
non-reproduction) unless the probe asserts that status; one tick at a time (`probe.lock`, a busy tick
exits 0); a key file is bound to its service by name (`key_name` = `<service>`, `<service>-…`,
`<service>_…`) and env/base URLs must be on `hosts` — both checked by the validator in CI
(`key_not_bound`, `foreign_env_url`) and again by the runner; `has_key` only stats the file, so dry
runs and `probe list` never read a value; unreadable key files count as missing; assertion details
show scalars only (objects/arrays by size); fact files keep their mode on rewrite.

---

### Task 1: Redaction + keys (TDD)

**Files:** Create `apifacts/probe/__init__.py`, `apifacts/probe/redact.py`, `apifacts/probe/keys.py`;
Test `tests/probe/test_redact.py`, `tests/probe/test_keys.py`.

- [ ] **Step 1: failing tests**

```python
def test_exact_secret_and_patterns_are_redacted():
    r = Redactor({"s3cr3t-value-123"})
    text = "k=s3cr3t-value-123 sk_test_abcdefgh123 Bearer abcdefghijklmnop1234 " + "a1" * 16
    out = r.text(text)
    for leaked in ("s3cr3t-value-123", "sk_test_abcdefgh123", "abcdefghijklmnop1234", "a1" * 16):
        assert leaked not in out

def test_words_and_urls_survive():
    r = Redactor(set())
    msg = "see https://docs.stripe.com/error-codes/idempotency-error for details"
    assert r.text(msg) == msg

def test_record_exempts_identifiers_but_not_exact_secrets():
    r = Redactor({"FAKEKEY12345678"})
    rec = {"probe_id": "af:x:probe:values-batch-get-v4-range-limit", "body_fingerprint": "ab" * 32,
           "steps": [{"error_string": "token FAKEKEY12345678 " + "0f" * 20}]}
    out = r.record(rec)
    assert out["probe_id"] == rec["probe_id"] and out["body_fingerprint"] == "ab" * 32
    assert "FAKEKEY12345678" not in json.dumps(out) and "0f" * 20 not in json.dumps(out)
```

  keys: `read_key("svc-test", tmp)` reads and strips `svc-test.key`; missing or whitespace-only file → `None`;
  `has_key` mirrors it without reading the value into the caller.
- [ ] **Step 2:** `uv run pytest -q tests/probe` → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: implement** `Redactor.text` (exact values longest-first, then patterns; generic base64 run
  replaced only if it contains a digit and a letter, hex run always), `Redactor.record` (recursive; keys in
  `EXEMPT_FIELDS` get `text_strict` = exact + `sk_` + `Bearer` only), `Redactor.line` (= `text_strict`).
- [ ] **Step 4:** run → PASS; `uv run ruff check .`; commit `feat(w2): redaction filter and key reader`.

### Task 2: Templating + JSON lookup (TDD)

**Files:** Create `apifacts/probe/templating.py`; Test `tests/probe/test_templating.py`.

- [ ] **Step 1: failing tests** — `{{run_uuid}}` same value in every step of a run; `{{now_rfc3339}}` =
  run start `YYYY-MM-DDTHH:MM:SSZ`; `{{step[1].json.data[0].id}}` resolves from step 1's JSON;
  a whole-string placeholder in a `json` body keeps the type (`{"n": "{{step[1].json.count}}"}` → `3`);
  unknown placeholder `{{env.HOME}}`, a later/current step `{{step[2]…}}` from step 2, a missing path, a
  non-JSON response → `TemplateError`; `render_path("/v1/items/{{step[1].json.id}}")` with id `a/b` →
  `/v1/items/a%2Fb`; `lookup({"a": [{"b": 1}]}, ".a[0].b") == 1`; `lookup(doc, "")` returns the doc.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement (`_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")`,
  path grammar `(\.[^.\[\]]+|\[\d+\])*`). **Step 4:** run → PASS; commit `feat(w2): probe templating`.

### Task 3: Assertions (TDD)

**Files:** Create `apifacts/probe/assertions.py`; Test `tests/probe/test_assertions.py`.

- [ ] **Step 1: failing tests** — one pass and one fail case per kind: `status`; `header` `present: true`,
  `present: false`, `equals`, `matches` (and invalid regex → fail, not crash); `json_path` `equals`
  (strict types: `True` ≠ `1`, `null` supported), `contains` (string substring, list membership), `exists`
  true/false; `body_contains`; `latency_ms: {lt}`; `schema_fingerprint` (value = sha256 of
  `'["a","b"]'` for `{"b":1,"a":2}`; non-object body → fail). Detail strings are short and say what was
  seen (`status 404 != 400`).
- [ ] **Step 2:** FAIL. **Step 3:** implement `evaluate(a, responses) -> AssertResult(step, kind, ok, detail)`.
- [ ] **Step 4:** PASS; commit `feat(w2): probe assertions`.

### Task 4: HTTP layer (TDD, `httpserver`)

**Files:** Create `apifacts/probe/http.py`; Test `tests/probe/test_http.py`.

- [ ] **Step 1: failing tests** against `httpserver`: GET with `query` (bools as `true`/`false`); POST
  `form`; POST `json`; probe `headers` sent; `User-Agent` equals `USER_AGENT` even if the probe sets one;
  auth kinds bearer/basic/header/query reach the server; `auth: none` sends no credential; a 302 is not
  followed; timeout → `StepResponse.error == "timeout"`; `prepare` refuses a rendered path that matches no
  template (`unregistered_template`), a prod POST (`prod_probe_not_readonly`) — and the server saw no
  request — and a keyed step whose probe env differs from `auth.env` (`auth_env_mismatch`).
- [ ] **Step 2:** FAIL. **Step 3:** implement (`httpx.Client(timeout=20, follow_redirects=False)`; stream,
  body capped at 1 MiB; latency via `time.perf_counter`).
- [ ] **Step 4:** PASS; commit `feat(w2): probe http steps with runtime re-checks`.

### Task 5: Budget state (TDD)

**Files:** Create `apifacts/probe/budget.py`; Test `tests/probe/test_budget.py`.

- [ ] **Step 1: failing tests** — never-run probe is due; after `record(probe, templates, vantage, t)` not due
  at `t + 299`, due at `t + 300`; another probe sharing a template is not due at `t + 10`; another vantage is
  due; state survives reopening the file; `last_run` returns `None` for unknown.
- [ ] **Step 2:** FAIL. **Step 3:** implement (two tables, `INSERT … ON CONFLICT DO UPDATE`, epoch seconds).
- [ ] **Step 4:** PASS; commit `feat(w2): probe budget state in sqlite`.

### Task 6: Loader + evidence updates (TDD)

**Files:** Create `apifacts/probe/loader.py`, `apifacts/probe/evidence.py`; Test
`tests/probe/test_loader.py`, `tests/probe/test_evidence.py`.

- [ ] **Step 1: failing tests** — loader: valid repo → models; a probe file with `env: prod` + POST is not
  loaded and reported (`prod_probe_not_readonly`); unknown service reported. Evidence: round-trip without
  change is byte-identical to the fixture fact; pass → counters/timestamp/vantage; three fails →
  `stale` + history `previous_status`; pass on stale → restored; fact with `dimensions.env: prod` and a
  sandbox probe → `other_dimension`, file unchanged; same for `account_state`; `official` fact on fail →
  counter only.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS; commit `feat(w2): registry loader and fact evidence updates`.

### Task 7: Runner + results (TDD, end to end)

**Files:** Create `apifacts/probe/runner.py`, `apifacts/probe/results.py`, `tests/probe/conftest.py`;
Test `tests/probe/test_runner.py`.

- [ ] **Step 1: failing tests** (each builds a repo in `tmp_path`, base URL overridden to `httpserver`):
  two-step probe with `{{step[1].json.id}}` in the path and a `sleep` step (fake sleeper records 0.5);
  `results.jsonl` has one line with `probe_id, vantage, env, started, outcome, steps[], asserts[]`;
  fact confirmed; failing assertion ×3 → fact `stale`; unexpected 429 → `error`, fact untouched;
  `expect_rate_limit: true` + 429 → assertions evaluated; missing key → `skipped:no_key`, no request,
  exit status ok; kill switch (`ops/KILL` file and `AGENTFACTS_KILL=1`) → zero requests, no files written;
  `--max 1` runs one of two due probes; `max_requests` defers a probe that does not fit; second tick within
  budget runs nothing, `--all` runs again; redaction: fake key in the keys dir, server echoes it in a
  whitelisted header and in the error body → key absent from every file under the state dir, facts dir
  and captured output; "different env never refutes": sandbox probe failing ×3 leaves a prod fact
  byte-identical; no `openai|anthropic|google.genai` import in `apifacts/probe`.
- [ ] **Step 2:** FAIL. **Step 3:** implement `run_tick`. **Step 4:** PASS; commit `feat(w2): probe runner tick`.

### Task 8: CLI + fixture + gitignore (TDD)

**Files:** Create `apifacts/probe/cli.py`, `tests/fixtures/probe-repo/…`; Modify `apifacts/cli.py`,
`.gitignore`; Test `tests/probe/test_cli.py`.

- [ ] **Step 1: failing tests** — `probe run --all --dry-run --root tests/fixtures/probe-repo --state-dir
  <tmp>` exits 0, prints `would-run af:example:probe:…` and `skipped:no_key af:examplepay:probe:…`, writes
  nothing; `probe list` prints every probe with `due`; `--vantage "Bad Name"` → exit 2; `apifacts validate
  tests/fixtures/probe-repo` exit 0.
- [ ] **Step 2:** FAIL. **Step 3:** implement; register `app.add_typer(probe_app, name="probe")`.
- [ ] **Step 4:** `uv run ruff check . && uv run pytest -q` → PASS; commit `feat(w2): probe run/list CLI and dry-run fixture`.

### Task 9: Review, PR, merge

- [ ] `git fetch origin && git rebase origin/main` (keep other packages' lines in `cli.py`/`pyproject.toml`).
- [ ] `uv run ruff check . && uv run pytest -q`; push; `gh pr create` ready, body with Summary, Test plan
  (outputs), "Assumptions that might be wrong"; `ccd_pr` bind + `set_monitor {auto_fix: true}`.
- [ ] `/code-review` of the local diff; fix every finding in the same PR; re-run checks; push.
- [ ] CI green → `gh pr merge --squash --delete-branch`; remove the worktree.

## Self-review against the spec

- 04 Done when: `probe run --due` executes due probes ✔ (T7, T8), results.jsonl ✔ (T7), evidence of
  referencing facts ✔ (T6, T7), budgets ✔ (T5, T7), kill switch ✔ (T7), keys by name ✔ (T1, T7), mock-server
  tests for every step kind (http GET/POST form/json/headers, sleep) and every assertion kind ✔ (T3, T4, T7).
- 04 Keys and secrets: `skipped:no_key` ✔, redaction patterns ✔, fake-key test ✔.
- 04 Kill switch and budgets: `ops/KILL`/`AGENTFACTS_KILL=1` ✔, per-service budget ✔, 50/tick ✔, honest UA ✔,
  20 s timeout ✔, stale after 3 ✔.
- 01 rule: different env/account_state never refutes ✔ (T6, T7). prod read-only ✔ (loader + T4 runtime).
- 09 W2 files ✔ (+ `evidence.py`, `cli.py` for separation).
