# W4 · Ingestion rules (D-085) + quorum + bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two PRs into `main`: PR-1 brings the W3 ingestion code in line with the seven rules Edouard
decided on 2026-10-20 (D-085, spec 03 steps 1–7); PR-2 adds `agentfacts quorum run` (observations →
`reported` fact drafts, probe scheduling, evidence refresh) and `agentfacts bot publish` (one PR of
fact/page changes, auto-merge when eligible) per spec 05.

**Architecture:** PR-1 only edits `agentfacts/api/` (signal extraction, store salt period, ingest gate,
unregistered-target metric) plus one data module of seed hosts. PR-2 adds two packages: `quorum`
(pure grouping/threshold → pure rules → YAML writer) reading `observations.sqlite` read-only, and
`bot` (git plumbing in a temporary worktree, `gh` behind an injectable runner). The probe runner
(W2) gets two minimal hooks: a "due request" flag in its budget sqlite, and `reported →
verified:server:<env>` on a passing run. No LLM anywhere; claims come from per-kind templates.

**Tech Stack:** Python 3.12, sqlite3, ruamel.yaml round-trip (W2 `evidence.py`), typer, git + gh CLIs
(gh mocked in tests; git used for real against a local bare repo in tests).

**Specs:** `docs/specs/03-check-contract.md` (steps 1–7, Q1–Q7), `05-ingestion-quorum-bot.md`,
`01-fact-schema.md` (fact, statuses), `04-probe-runner.md` (budget, kill switch),
`08-ops-autonomy.md` (timers, digest), `09-work-breakdown.md` § W4 + Process; `docs/decisions.md`
2026-10-20 (seven rules).

---

## Rule audit (what W3 already does, checked against the decided text)

| Rule | W3 state | Action |
|------|----------|--------|
| (1) URLs allowed on `hosts` + `doc_hosts` | `on_vendor_domain(url, info.vendor_hosts)`; vendor_hosts = hosts + doc_hosts | test with a `doc_hosts` service (pypi fixture gets `doc_hosts`) |
| (2) prompt markers | ignore all/any/the previous, disregard all/any/the previous, system:, assistant:, `<|im_start|>`, `[INST]` | widen `disregard … previous` to ≤ 3 words in between (spec "…"); API-level drop tests for every marker |
| (3) IPv4 /16, IPv6 /32 | `network_of` | API-level test: same /32 → same reporter, other /32 → other |
| (4) JSON without whitelisted message → status only | falls back to first line of the excerpt | change `extract_signal`; fix W3 test that pinned the fallback |
| (5) pre-flight not stored | stored with status NULL | store only with `error` and a non-empty signal |
| (6) weekly salt, Monday 00:00 UTC | daily salt | `salt_period()` + `Store.period_salt()`; boundary tests |
| (7) host kept only for seed candidates | one anonymous counter | `unregistered_target:<host>` / `unregistered_target:other` (+ the plain total, kept for W8) |
| daily cap 1 000 / net | `DAILY_CAP = 1000`, `Store.add_observation(daily_cap=…)` | test at the real constant on the store |

## File map

| File | PR | Responsibility |
|------|----|----------------|
| `agentfacts/api/normalize.py` | 1 | `extract_signal`: JSON-shaped excerpt without whitelisted message → no string; `disregard … previous` |
| `agentfacts/api/store.py` | 1 | `salt_period(day) -> date` (Monday), `Store.period_salt(period)` (replaces `daily_salt`) |
| `agentfacts/api/schema.sql` | 1 | comments: salts are per period |
| `agentfacts/api/seed_hosts.py` | 1 | `SEED_HOSTS` (candidate → API hosts), `metric_host(host) -> str` |
| `agentfacts/api/app.py` | 1 | ingest gate (error + signal), period salt, labelled unregistered metric |
| `tests/api/test_ingestion_rules.py` | 1 | one test group per rule (1)–(7) + cap |
| `tests/api/test_seed_hosts.py` | 1 | keys ⊆ candidates.py, hostnames valid, registered services covered |
| `tests/api/*` (existing) | 1 | update tests that pinned old behaviour |
| `agentfacts/quorum/group.py` | 2 | `period_window`, `load_observations` (ro sqlite), `Group`, `group_observations`, `meets_quorum` |
| `agentfacts/quorum/rules.py` | 2 | `infer_kind`, `claim_for`, `slug_base`, `unique_slug` |
| `agentfacts/quorum/draft.py` | 2 | `draft_fact`, `matching_probe`, `covering_fact`, `refresh_fact` |
| `agentfacts/quorum/run.py` | 2 | `run_quorum(...) -> QuorumReport` (orchestration, kill switch, dry run) |
| `agentfacts/quorum/cli.py` | 2 | `agentfacts quorum run [--since-period DATE] [--dry-run] [--db] [--root] [--state-dir]` |
| `agentfacts/bot/collect.py` | 2 | changed fact files vs HEAD, drift guard vs origin/main, eligibility |
| `agentfacts/bot/pr.py` | 2 | branch name, PR body table, temp worktree commit/push, `gh` calls |
| `agentfacts/bot/cli.py` | 2 | `agentfacts bot publish [--dry-run]` |
| `agentfacts/probe/budget.py` | 2 | `request_due`, `requested`; `record` clears the request |
| `agentfacts/probe/runner.py` | 2 | requested probes sort first (budget still applies) |
| `agentfacts/probe/evidence.py` | 2 | pass on `reported` → `verified:server:<env>`; public `save_fact` |
| `agentfacts/api/facts_index.py` | 2 | `_hashes` → public `fact_hashes` (quorum reuses check()'s matching) |
| `agentfacts/cli.py` | 2 | `add_typer` for quorum and bot |
| `tests/quorum/*`, `tests/bot/*`, `tests/probe/test_due_requests.py` | 2 | below |

---

# PR-1 · ingestion rules per D-085 (branch `feat/w4-ingestion-rules`)

### Task 1: rule (4) — JSON body without a whitelisted message keeps only the status

**Files:** Modify `agentfacts/api/normalize.py` (`extract_signal`); Test `tests/api/test_ingestion_rules.py`, `tests/api/test_normalize.py::test_non_whitelisted_fields_are_ignored`

- [ ] **Step 1: failing tests**

```python
@pytest.mark.parametrize("excerpt", [
    '{"error": {"code": "x"}, "message": "top"}',        # JSON, message not whitelisted
    '{"error": {"code": "x", "message": "cut here',       # truncated JSON
    '  [{"detail": "nope"}]',                             # JSON array
])
def test_json_without_whitelisted_message_has_no_string(excerpt):
    s = extract_signal(400, excerpt, ("error.message",))
    assert (s.status, s.raw_string, s.normalized, s.error_hash) == (400, None, None, None)
    assert not s.empty

@pytest.mark.parametrize("excerpt", ["[ERROR] upstream timed out", "[2026-10-20] boom"])
def test_bracketed_text_is_not_json(excerpt):
    assert extract_signal(500, excerpt, ()).raw_string == excerpt

def test_json_body_stored_as_status_only(client, db_path):   # API level: row has status, no string
```

- [ ] **Step 2:** `uv run pytest tests/api/test_ingestion_rules.py -q` → FAIL (first line kept).
- [ ] **Step 3: implement** `_json_shaped(excerpt)`: stripped starts with `{`, or with `[` followed
  (after spaces) by `{ [ " ]` or end. In `extract_signal`: `raw = message if json_shaped else
  (message or _first_line(excerpt))`. Update the W3 test to expect `raw_string is None`.
- [ ] **Step 4:** tests pass. **Step 5:** commit `W4: rule 4 — JSON without whitelisted message keeps status only`.

### Task 2: rule (5) — pre-flight calls and empty signals are never stored

**Files:** Modify `agentfacts/api/app.py` (`_check`); Test `tests/api/test_ingestion_rules.py`; update
`test_check_contract.py::test_preflight_url_lists_template_and_service_facts` (stored False, 0 rows),
`test_signal_not_extractable` (0 rows), `test_default_deny.py::test_query_string…` (send an error).

- [ ] **Step 1: failing tests**

```python
def test_preflight_on_a_template_is_answered_not_stored(client, rows, counters):
    body = client.post("/v0/check", json={"target": {"method": "POST", "url": STRIPE_PI}}).json()
    assert body["unknown"] == {"reason": None, "stored_as_observation": False}
    assert body["facts"]  # still answered
    assert rows() == 0 and "stored" not in counters()

def test_error_without_any_signal_is_not_stored(client, rows):
    payload = {"target": {"method": "POST", "url": STRIPE_PI}, "error": {"body_excerpt": " "}}
    assert client.post("/v0/check", json=payload).json()["unknown"]["stored_as_observation"] is False
    assert rows() == 0
```

- [ ] **Step 2:** FAIL. **Step 3:** in `_check`, call `_ingest` only when `signal is not None and not
  signal.empty`. **Step 4:** pass (fix the three W3 tests). **Step 5:** commit.

### Task 3: rule (6) — salt per week, Monday 00:00 UTC

**Files:** Modify `agentfacts/api/store.py`, `agentfacts/api/app.py`, `agentfacts/api/schema.sql`
(comments); Test `tests/api/test_store.py` (replace daily-salt tests), `tests/api/test_ingestion_rules.py`.

- [ ] **Step 1: failing tests**

```python
@pytest.mark.parametrize("day, monday", [("2026-10-19", "2026-10-19"), ("2026-10-25", "2026-10-19"),
                                         ("2026-10-26", "2026-10-26"), ("2026-01-01", "2025-12-29")])
def test_salt_period_starts_monday(day, monday):
    assert salt_period(date.fromisoformat(day)) == date.fromisoformat(monday)

def test_period_salt_rotates_and_old_salts_are_deleted(store): ...
def test_same_network_keeps_its_id_all_week_and_changes_next_monday(make_client, db_path):
    # utcnow injected: Sun 2026-10-25T23:59:59Z vs Mon 2026-10-19T00:00:00Z → same hash;
    # Mon 2026-10-26T00:00:00Z → different hash
```

- [ ] **Step 2:** FAIL (no `salt_period`). **Step 3:** `salt_period(day) = day - timedelta(day.weekday())`;
  `Store.period_salt(period: str)` = old `daily_salt` body (column `day` now holds the period's Monday);
  `_ingest` uses `period_salt(salt_period(now.date()).isoformat())`. **Step 4:** pass. **Step 5:** commit.

### Task 4: rule (7) — unregistered-target metric keeps only seed-candidate hosts

**Files:** Create `agentfacts/api/seed_hosts.py`; Modify `agentfacts/api/app.py` (default-deny branch);
Test `tests/api/test_seed_hosts.py`, `tests/api/test_ingestion_rules.py`, update
`tests/api/test_default_deny.py` counters expectation.

- [ ] **Step 1: failing tests**

```python
def test_candidate_host_is_kept_in_the_metric(client, counters):
    client.post("/v0/check", json={"target": {"method": "GET", "url": "https://api.notion.com/v1/pages/x"}})
    assert counters() == {"unregistered_target": 1, "unregistered_target:api.notion.com": 1}

@pytest.mark.parametrize("target", [{"method": "GET", "url": "https://intranet.acme.corp/v1/x"},
                                    {"url": "npm:left-pad@1.3.0"}, {"url": "not a url at all"},
                                    {"method": "GET", "url": "https://acme.api.notion.com/v1/x"}])
def test_other_hosts_count_as_other(client, counters, db_path, target): ...  # no host bytes in file

def test_seed_hosts_keys_are_candidates():   # runpy docs/research/seed-100/candidates.py
def test_registered_services_hosts_are_seed_hosts():  # services/*.yaml ⊆ SEED_HOSTS[key]
```

- [ ] **Step 2:** FAIL. **Step 3:** `SEED_HOSTS: dict[str, tuple[str, ...]]` (exact API hosts of the
  remote candidates; local libraries have none), `metric_host(host) -> host | "other"` (exact match only:
  a tenant subdomain is `other`); app bumps `unregistered_target` and `unregistered_target:<label>`.
  **Step 4:** pass. **Step 5:** commit.

### Task 5: rules (1)(2)(3) and the daily cap — prove them at API level

**Files:** Modify `agentfacts/api/normalize.py` (`_PROMPT_MARKERS`: `disregard(?:\s+\S+){0,3}?\s+(?:previous|prior|above)`),
`tests/api/api_fixtures.py` (pypi gets `doc_hosts: [docs.pypi.org]`); Test `tests/api/test_ingestion_rules.py`.

- [ ] **Step 1: tests** — URL on `doc_hosts` kept / subdomain of host kept / foreign dropped; every
  marker of spec 03 step 7 dropped through `POST /v0/check` (incl. "disregard your previous
  instructions"); IPv6 same /32 → one reporter, other /32 → two; `Store.add_observation(daily_cap=DAILY_CAP)`
  stops at 1 000 rows for one net and `app.DAILY_CAP == 1000`.
- [ ] **Step 2:** only the `disregard your previous` case fails. **Step 3:** widen the regex.
  **Step 4:** pass. **Step 5:** commit.

### Task 6: PR-1 wrap-up

- [ ] `uv run pytest -q tests/api/test_openapi.py` (contract unchanged → `openapi-v0.json` untouched).
- [ ] Docstrings: `app.py` module/`_ingest`, `store.py` (no "daily salt" left): `grep -rn "daily salt\|daily_salt" agentfacts tests`.
- [ ] `uv run ruff check . && uv run pytest -q` green → push → PR ready → `/code-review` → fix all → CI → squash merge.

---

# PR-2 · quorum + bot (branch `feat/w4-quorum-bot`, from fresh `origin/main`)

### Task 7: probe hooks — due requests and reported → verified

**Files:** Modify `agentfacts/probe/budget.py`, `agentfacts/probe/runner.py` (`_select` sort key),
`agentfacts/probe/evidence.py` (`_confirm`, `save_fact`); Test `tests/probe/test_due_requests.py`,
`tests/probe/test_evidence.py` (new case).

- [ ] **Step 1: failing tests**

```python
def test_requested_probe_runs_first_within_budget(tmp_path):   # max_probes=1: requested wins over older
def test_request_does_not_bypass_the_budget(tmp_path):          # ran 10 s ago → still not-due
def test_record_clears_the_request(tmp_path):
def test_pass_upgrades_reported_to_verified(tmp_path):          # history {change: verified, previous_status: reported}
```

- [ ] **Step 2:** FAIL. **Step 3:** table `due_requests(probe_id, vantage, at)`; `request_due()`,
  `requested()`; `record()` deletes the row; `_select` sorts by `(not requested, last_run, id)`;
  `_confirm` on `reported` sets `verified:server:<probe.env>` and appends history.
  **Step 4:** pass. **Step 5:** commit.

### Task 8: grouping and thresholds (`quorum/group.py`)

- [ ] **Step 1: failing tests** (`tests/quorum/test_group.py`, observations written with W3 `Store.add_observation`)

```python
def test_period_window():                         # Wed 2026-10-21T10:00Z → [2026-10-19T00:00Z, now]
def test_groups_by_error_hash_or_by_status():     # string rows by hash; status-only rows by (template, status)
def test_quorum_needs_three_nets_and_two_clients(): # 3 nets + 2 UA classes → yes; 2 nets → no; 3 nets 1 UA 1 SDK → no; 1 UA + 2 SDK packages → yes
def test_rows_outside_the_period_are_ignored():
def test_missing_db_reads_as_empty():             # dry run on a fresh host: nothing, no file created
```

- [ ] **Step 3: implement** `Group(service, method, path_template, error_hash, normalized, status, nets,
  ua_classes, sdk_packages, env_guesses, first_seen)`; `meets_quorum(g) = len(nets) >= 3 and
  max(len(ua_classes), len(sdk_packages)) >= 2`. Status of a string group = most frequent status.
- [ ] **Step 4–5:** pass, commit.

### Task 9: rules (`quorum/rules.py`)

- [ ] **Step 1: failing tests** (`tests/quorum/test_rules.py`)

```python
@pytest.mark.parametrize("status, normalized, headers, kind", [
    (429, None, (), "rate_limit"), (400, "x", ("Retry-After",), "rate_limit"),
    (200, None, (), "silent_behavior"), (200, "x", (), "error_meaning"),
    (401, "x", (), "auth_quirk"), (403, None, (), "auth_quirk"),
    (410, None, (), "deprecation"), (400, "x", ("Sunset",), "deprecation"),
    (404, "not found", (), "error_meaning"), (None, "boom", (), "error_meaning")])
def test_infer_kind(...)
def test_claim_templates_per_kind_and_length_cap():  # ≤ 300 chars, normalized string quoted
def test_slug_base():  # 400 + "keys for idempotent requests can only be used..." → "400-keys-for-idempotent-requests-can-only"
def test_unique_slug_dedups_with_suffix():  # taken {a, a-2} → a-3; "index" never used
```

- [ ] **Step 3–5:** implement, pass, commit.

### Task 10: drafts, coverage, refresh, probe match (`quorum/draft.py`)

- [ ] **Step 1: failing tests** (`tests/quorum/test_draft.py`, tmp repo from W1 fixtures + a probe)
  - draft document validates with `agentfacts validate` (via `validate_paths`), status reported,
    provenance `observation_quorum`, `fixes: [{action: none_known, reason_kind: investigating}]`;
  - a group whose hash matches a fact (error_string or normalized) is covered; status-only group
    covered by a fact with the same template + status; retracted facts cover but are not refreshed;
  - refresh raises `evidence.observations` (never lowers), on `reported` sets `last_confirmed`
    at most once per day, leaves the rest of the file byte-identical;
  - probe match: step path instantiates the template with the same method, assertion on that step
    has the status or a string contained in the normalized error; env from observations must equal
    the probe env (unknown env → the probe's); the draft cites the probe and takes its dimensions.
- [ ] **Step 3–5:** implement, pass, commit.

### Task 11: `quorum run` orchestration + CLI

- [ ] **Step 1: failing tests** (`tests/quorum/test_run.py`, `tests/quorum/test_cli.py`)
  - fixture above quorum → exactly one draft file, probe due-requested, report lists it;
  - fixture below quorum → nothing written, nothing requested;
  - second run → no new draft (dedup by coverage), observations unchanged;
  - `--dry-run` → plan printed, no file, no state dir;
  - kill switch (`ops/KILL`, `AGENTFACTS_KILL=1`) → exit 0, nothing done.
- [ ] **Step 3:** `run_quorum(root, db, state_dir, now, vantage, dry_run, environ) -> QuorumReport`;
  CLI prints one line per group (`draft|refresh|covered|below`), exit 0/2.
- [ ] **Step 4–5:** pass, commit.

### Task 12: bot (`bot/collect.py`, `bot/pr.py`, `bot/cli.py`)

- [ ] **Step 1: failing tests** (`tests/bot/test_collect.py`, `tests/bot/test_pr.py`, `tests/bot/test_cli.py`;
  real git with a local bare `origin`, `gh` replaced by a recorder)
  - changed + untracked files under `facts/` are collected; anything outside `facts/` is ignored;
  - a file changed on `origin/main` since HEAD is skipped (drift guard) and reported;
  - eligibility: all facts `verified:*` or (`reported` + `observation_quorum`) and author `bot` → auto;
    otherwise (stale, human author, deletion) → no auto-merge;
  - PR body: table `id | kind | status | evidence` + footer; deterministic;
  - publish: branch `bot/facts-<date>-<n>` (n = 1 + existing remote branches of the day), commit by
    `agent-facts-bot` with `Signed-off-by` carrying the vantage, only `facts/` + regenerated `pages/`,
    pushed to the bare origin; `gh pr create --label facts`, `gh pr merge --auto --squash` only when eligible;
  - an open bot PR → nothing published (changes stay for the next run);
  - `--dry-run` → no branch, no push, no gh call; kill switch → exit 0.
- [ ] **Step 3–5:** implement, pass, commit.

### Task 13: PR-2 wrap-up

- [ ] Demo: `agentfacts quorum run --dry-run` on a fixture DB and `agentfacts bot publish --dry-run`
  (outputs go to the PR body and the report).
- [ ] `uv run ruff check . && uv run pytest -q && uv run agentfacts validate && uv run agentfacts pages build --check`.
- [ ] push → PR ready → `/code-review` → fix all → CI → squash merge → hand-over note for W8
  (`side-session-notes/af-w4-handover.md`) → worktree removed → state journal.

## Self-review against spec 05

- Quorum window = current salt period: Task 8 (`period_window`) + Task 3 (salt period) share `salt_period`.
- Thresholds ≥ 3 nets, ≥ 2 UA classes or SDK packages: Task 8.
- Already a fact → refresh `evidence.observations`: Task 10. New → draft with status/kind/claim/fixes/slug: Tasks 9–10.
- Probe scheduling + reported → verified: Tasks 7 and 10; "needs a probe" is listed by `quorum run` (digest is W8).
- Bot: branch, one PR, table, label, author, never code, auto-merge rule, kill switch: Task 12.
- Abuse: 1 000/day/net (Task 5), foreign URL / prompt markers (Task 5).
