# Quiet bot + sec variant 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two PRs into `main`. PR-1 (`fix/bot-quiet`) stops the runner and the bot from turning
every 15-minute probe confirmation into a commit, a PR, a CI run, a deploy and a journal line
(incident 2026-10-20..24: 62 bot PRs, 137 CI runs, Actions spending limit spent). PR-2
(`fix/bot-token-verified-only`) implements variant 1 of the sec card 2026-10-23 (D-089):
auto-merge only for `verified:*`, the bot on its own token, hardened user units.

**Architecture:** The runner keeps confirmation counters in a local ledger
(`var/evidence-pending.sqlite`) and writes a fact's YAML only on a status change or a first
confirmation from a new vantage; a daily `probe run --refresh-evidence` flushes the ledger into the
YAML and leaves a marker. A fact's *substance* (everything but the moving evidence counters) decides
what is urgent: the bot opens a PR at once for substance changes and one "daily evidence refresh"
PR per day after the refresh marker; the deploy journal writes a line only when the substance of
the registry changed between the previous and the new sha. PR-2 changes the eligibility rule,
passes the bot key as `GH_TOKEN` (gh) and through an env-only credential helper (git), and adds
the systemd hardening that works for user units on illouminus.

**Tech Stack:** Python 3.12, sqlite3, ruamel.yaml round-trip, typer, git + gh (gh faked in tests,
git real against a bare repo), bash 3.2-compatible `ops/deploy.sh`, systemd user units.

**Specs:** `docs/specs/04-probe-runner.md`, `05-ingestion-quorum-bot.md`, `08-ops-autonomy.md`,
`09-work-breakdown.md` (Process); sec card `state/tasks/2026-10-23-sec-agent-facts-quorum-automerge-and-bot-rights.md`;
decisions D-088, D-089.

---

## Findings that shape the plan

| Finding | Source | Consequence |
|---------|--------|-------------|
| Every pass rewrites `last_confirmed`/`confirmations` | `probe/evidence.py::_confirm`, host `git diff` (39 files dirty) | ledger + daily flush |
| Bot treats any byte change as "changed fact" | `bot/collect.py::changed_facts` | classify substance vs counters |
| Journal line per deploy, whatever changed | `ops/state_journal.py::main` | git-based substance delta, `--prev` |
| 8 search-probe failures = `403 API rate limit exceeded`, `x-ratelimit-used: 10` of 10 at our call | host `var/results.jsonl` | the IP's 10/min search limit is spent by other clients (our two probes share one template at 1 800 s, ≤ 2 calls/h); a smaller budget or merging the probes changes nothing. Minimal fix: a 403 with `X-RateLimit-Remaining: 0` is a rate-limit answer → `error` (not evidence), like an unexpected 429 |
| User-unit sandboxing on illouminus | `systemd-run --user` experiments 24.10 | Ubuntu 24.04, `kernel.apparmor_restrict_unprivileged_userns=1`: mount-namespace options (`ProtectSystem`, `ProtectHome`, `PrivateTmp`, `ReadWritePaths`, `InaccessiblePaths`, `TemporaryFileSystem`, `BindReadOnlyPaths`, `ProtectProc`, `ProtectKernel*`) are ignored or fail with 226/NAMESPACE ("Failed to set up mount namespacing: Operation not supported"). Seccomp/prctl options apply (`NoNewPrivs: 1`, `Seccomp: 2` verified). Per-file key access is impossible in user units here → documented, follow-up |
| `gh auth git-credential` (personal token) is the URL helper for github.com in `~/.gitconfig` | host | git calls of the bot must reset the helper list and use an env-only helper with the bot token |

## File map

| File | PR | Responsibility |
|------|----|----------------|
| `apifacts/schema/substance.py` | 1 | `VOLATILE_EVIDENCE`, `substance(doc)` — what a fact says minus moving counters |
| `apifacts/probe/ledger.py` | 1 | `Pending`, `EvidenceLedger` (sqlite in the state dir) |
| `apifacts/probe/evidence.py` | 1 | `apply_outcome(..., ledger=None)`: write only on status change / new vantage; `refresh_from_ledger` |
| `apifacts/probe/runner.py` | 1 | ledger in the tick; `refresh_evidence()` + marker; 403 rate-limit → error |
| `apifacts/probe/cli.py` | 1 | `probe run --refresh-evidence` |
| `apifacts/bot/collect.py` | 1 | `FactRow.substantive` |
| `apifacts/bot/pr.py` | 1/2 | hold evidence-only changes until the daily refresh; daily PR title; bot state; (2) eligibility, label, token |
| `apifacts/bot/cli.py` | 1/2 | `--state-dir`, `holding` summary; (2) missing token message |
| `apifacts/bot/token.py` | 2 | read `agent-facts-bot` key, env for gh and git, redaction |
| `ops/state_journal.py` | 1 | `--prev`: delta of statuses + new/changed/removed ids from git; nothing for counter-only |
| `ops/deploy.sh` | 1/2 | pass `--prev`; link new unit files before daemon-reload; (2) fetch without the personal helper |
| `ops/systemd/agentfacts-refresh.{service,timer}` | 1 | daily 03:00 Europe/Paris flush |
| `ops/systemd/*.service` | 2 | hardening that applies to user units |
| `ops/README.md`, `docs/specs/04,05,08` | 1/2 | honest lines |
| tests: `tests/probe/test_ledger.py`, `tests/probe/test_quiet_evidence.py`, `tests/bot/test_quiet_bot.py`, `tests/bot/test_bot_token.py`, `tests/ops/test_state_journal.py`, `tests/ops/test_deploy_sh.py`, `tests/ops/test_units.py` | 1/2 | |

---

# PR-1 · `fix/bot-quiet`

### Task 1: substance of a fact

**Files:** Create `apifacts/schema/substance.py`; Test `tests/schema/test_substance.py`

- [ ] **Step 1: failing test**

```python
from apifacts.schema.substance import VOLATILE_EVIDENCE, substance

def test_counters_are_not_substance():
    a = {"id": "x", "status": "verified:server:prod",
         "evidence": {"probe": "p", "confirmations": 1, "last_confirmed": "t1",
                      "stale_counter": 0, "vantages": ["a"], "observations": 0}}
    b = {**a, "evidence": {**a["evidence"], "confirmations": 9, "last_confirmed": "t2",
                           "stale_counter": 2, "vantages": ["a", "b"], "observations": 4}}
    assert substance(a) == substance(b)
    assert substance({**a, "status": "stale"}) != substance(a)
    assert substance({**a, "evidence": {**a["evidence"], "probe": "q"}}) != substance(a)
    assert VOLATILE_EVIDENCE == {"last_confirmed", "confirmations", "stale_counter", "vantages",
                                 "observations"}
```

- [ ] **Step 2:** `uv run pytest tests/schema/test_substance.py -q` → FAIL (module missing)
- [ ] **Step 3:** implement `substance(doc) -> dict` (plain copy, evidence without volatile keys)
- [ ] **Step 4:** test passes; commit `schema: substance of a fact (counters excluded)`

### Task 2: evidence ledger

**Files:** Create `apifacts/probe/ledger.py`; Test `tests/probe/test_ledger.py`

`Pending(confirmations: int = 0, last_confirmed: str | None = None, stale_counter: int | None = None)`;
`EvidenceLedger(path, read_only=False)` with `get(fact_id)`, `put(fact_id, pending)`, `clear(fact_id)`,
`items()`; context manager; file `<state-dir>/evidence-pending.sqlite` (`LEDGER_FILE`).
Read-only mode never creates the file (dry runs), like `BudgetState`.

- [ ] tests: round trip put/get, clear, items sorted, read-only on a missing file returns None and
      creates nothing → FAIL → implement → PASS → commit `probe: evidence ledger`

### Task 3: quiet `apply_outcome`

**Files:** Modify `apifacts/probe/evidence.py`; Test `tests/probe/test_quiet_evidence.py`

Rules with a ledger: overlay pending counters on the document, apply the transition, then
- write the YAML (with the overlaid counters) and clear the ledger entry when the change is
  `verified`, `restored`, `stale`, or a pass from a vantage not yet in the YAML;
- otherwise store the effective counters in the ledger (confirmations as a delta over the YAML).
`refresh_from_ledger(path, ledger) -> str` (`refreshed`, `unchanged`, `untouched`, `invalid`)
overlays and writes, then clears. Without a ledger, `apply_outcome` behaves as before (tests of W2).

- [ ] **Step 1: failing tests**

```python
def test_twenty_passes_leave_the_yaml_alone(repo, tmp_path):
    path = repo.fact()
    before = path.read_bytes()
    with EvidenceLedger(tmp_path / "l.sqlite") as ledger:
        for i in range(20):
            assert apply_outcome(path, SANDBOX, "pass", "illouminus", NOW + i * STEP,
                                 ledger=ledger) == "confirmed"
        assert path.read_bytes() == before
        assert ledger.get("af:acme:items-list-ok") == Pending(20, rfc3339(NOW + 19 * STEP), 0)

def test_status_change_writes_with_the_pending_counters(repo, tmp_path): ...
    # 5 passes (ledger), 3 fails → "stale", YAML: status stale, confirmations 6, stale_counter 3
def test_new_vantage_writes_once(repo, tmp_path): ...  # freebox pass → YAML vantages + counters
def test_refresh_flushes_and_clears(repo, tmp_path): ...  # 3 passes, refresh → confirmations 4
def test_failures_below_three_stay_in_the_ledger(repo, tmp_path): ...
```

- [ ] **Step 2:** run → FAIL; **Step 3:** implement; **Step 4:** `uv run pytest tests/probe -q` PASS
- [ ] **Step 5:** commit `probe: confirmations go to a ledger, YAML only on status change`

### Task 4: runner uses the ledger; `--refresh-evidence`; 403 rate limit

**Files:** Modify `apifacts/probe/runner.py`, `apifacts/probe/cli.py`; Test `tests/probe/test_runner.py`, `tests/probe/test_probe_cli.py`

- `run_tick` opens `EvidenceLedger(state_dir / LEDGER_FILE)` (not in dry runs) and passes it.
- `refresh_evidence(root, state_dir, *, clock, environ, dry_run) -> RefreshReport` (kill switch,
  tick lock, every ledger entry → its fact by id; unknown id dropped; marker
  `<state-dir>/evidence-refresh.json` `{"refreshed": rfc3339, "written": n}` unless dry run).
- `_execute`: `403` with `X-RateLimit-Remaining: 0` on a step that neither sets
  `expect_rate_limit` nor asserts status 403 → `error` "rate limited (403, x-ratelimit-remaining: 0)".
- CLI: `apifacts probe run --refresh-evidence [--dry-run]` → `evidence refresh: N written, M unchanged`.

- [ ] tests: 20 ticks against `httpserver` → fact file bytes unchanged, results.jsonl 20 lines;
      3 failing ticks → YAML stale; refresh writes and leaves the marker; 403+remaining 0 → `error`,
      fact untouched; 403 asserted (solana-style) stays `pass`; CLI refresh output → FAIL → implement → PASS
- [ ] commit `probe: --refresh-evidence and quiet ticks; a rate-limited 403 is not evidence`

### Task 5: bot holds counter-only changes for the daily PR

**Files:** Modify `apifacts/bot/collect.py`, `apifacts/bot/pr.py`, `apifacts/bot/cli.py`; Test `tests/bot/test_quiet_bot.py`

- `FactRow.substantive`: new, deleted, invalid, or `substance(local) != substance(HEAD)`.
- `publish(..., state_dir=None)`: if no row is substantive, open a PR only when
  `evidence-refresh.json` is newer than `bot-state.json:evidence_refresh` and
  `bot-state.json:evidence_day != today`; else `PublishReport("holding")` (no fetch, no gh).
  Title/commit `facts: daily evidence refresh (<today>)`; after opening, write bot state.
- CLI `--state-dir` (default `<root>/var`), summary `holding: …`.

- [ ] **Step 1: failing end-to-end test** (real git, real runner against `httpserver`, fake gh)

```python
def test_twenty_ticks_open_no_pr(world):
    for _ in range(20):
        world.tick(ok=True)
        assert world.publish().action in ("nothing", "holding")
    assert world.gh.verbs().count("pr create") == 0
    assert world.git_status_facts() == ""

def test_status_change_opens_one_pr(world): ...      # 3 failing ticks → stale → 1 PR
def test_daily_refresh_opens_one_pr(world): ...      # 20 ticks, refresh, publish → 1 PR titled
                                                     # "facts: daily evidence refresh (2026-10-21)";
                                                     # publish again same day → holding, still 1
```

- [ ] run → FAIL → implement → `uv run pytest tests/bot -q` PASS → commit
      `bot: PR at once only for new facts and status changes; counters once a day`

### Task 6: journal only when the registry's substance changed

**Files:** Modify `ops/state_journal.py`, `ops/deploy.sh`; Test `tests/ops/test_state_journal.py`, `tests/ops/test_deploy_sh.py`

- `--prev <sha>`: `registry_delta(root, prev, sha)` from `git diff --name-status prev sha -- facts`,
  both blobs via `git show`, compared by `substance`. Empty delta → print
  `journal: registry unchanged since <prev7> (evidence only); nothing written`, exit 0.
  Otherwise the entry: `- main abc1234 «subj»: фактов 55 (+2; verified 41 (+2), official 14, …);
  новые: id, …; изменены: id (verified → stale), …; удалены: …; /healthz ok.`
- deploy.sh: `journal "$app" "$sha" "$prev"` passes `--prev`.

- [ ] tests on a git fixture: evidence-only commit → nothing written, no state-commit call;
      new fact + status change → one entry with the delta; deploy.sh passes `--prev`
      (stub python records argv) → FAIL → implement → PASS → commit `ops: journal only on registry change`

### Task 7: daily refresh unit, unit linking on deploy

**Files:** Create `ops/systemd/agentfacts-refresh.service`, `ops/systemd/agentfacts-refresh.timer`; Modify `ops/deploy.sh`, `ops/README.md`; Test `tests/ops/test_units.py`, `tests/ops/test_deploy_sh.py`

- service: `ExecStart=%h/apps/agent-facts/.venv/bin/apifacts probe run --refresh-evidence --root %h/apps/agent-facts`
- timer: `OnCalendar=*-*-* 03:00:00 Europe/Paris`, `Persistent=true`
- deploy.sh `switch()`: when `ops/systemd` changed, `systemctl --user link` every unit file not yet in
  `~/.config/systemd/user`, then `daemon-reload` (enabling stays a deliberate step).

- [ ] tests → FAIL → implement → PASS → commit `ops: daily evidence refresh timer; deploy links new units`

### Task 8: specs and README

- [ ] spec 04 (Execution): counters → ledger, YAML on status change / new vantage / daily refresh,
      incident line; rate-limited 403 → error.
- [ ] spec 05 (Bot): PR at once for new facts and substance changes, counter-only changes one PR a day.
- [ ] `ops/README.md`: refresh timer row, enable command.
- [ ] `uv run ruff check . && uv run pytest -q` → green; commit `docs: quiet runner and bot (incident 24.10)`

### Task 9: ship PR-1

- [ ] rebase on `origin/main`; push; `gh pr create` ready; `/code-review` on the local diff; fix every
      finding; CI green; squash merge; deploy log; enable `agentfacts-refresh.timer` on the host.

# PR-2 · `fix/bot-token-verified-only` (from fresh `origin/main`)

### Task 10: auto-merge only for `verified:*`

**Files:** Modify `apifacts/bot/collect.py`, `apifacts/bot/pr.py`; Test `tests/bot/test_bot.py`

- `_eligible`: `status in VERIFIED_STATUSES and author == "bot"` (reported from quorum no longer).
- PR without auto-merge gets labels `facts` and `needs-review` (label created with `--force`).

- [ ] tests: quorum `reported` draft → opened, `auto` false, `pr merge` not called, `--label needs-review`
      in `pr create`; all verified → `pr merge --auto --squash`, no `needs-review` → FAIL → implement → PASS → commit

### Task 11: the bot's own token

**Files:** Create `apifacts/bot/token.py`; Modify `apifacts/bot/pr.py`, `apifacts/bot/cli.py`, `ops/deploy.sh`; Test `tests/bot/test_bot_token.py`, `tests/ops/test_deploy_sh.py`

- `BOT_KEY = "agent-facts-bot"`; `BotAuth.load(keys_dir) -> BotAuth` (reads with `probe.keys.read_key`);
  missing → `MissingToken` ("put it with keyput agent-facts-bot; the bot never falls back to the
  personal gh login").
- `BotAuth.gh_env(base)`: `GH_TOKEN`, `GH_PROMPT_DISABLED=1`; `BotAuth.git_env(base)`:
  `GIT_CONFIG_COUNT=2`, helper reset + `!f() { test "$1" = get || exit 0; echo username=x-access-token; echo "password=$GH_TOKEN"; }; f`,
  `GIT_TERMINAL_PROMPT=0`; anonymous variant (no token) for dry runs: helper reset only.
- `BotAuth.redact(text)` via `Redactor.for_keys`; every `GitError` from remote git and gh is redacted.
- deploy.sh: `git -c credential.helper= fetch` (public repo; never the personal helper).

- [ ] tests: missing key → exit 1 with the message, no gh call; gh env carries the token, argv never
      does; git push runs with the helper env (a recording `git` wrapper is not needed: the bare
      origin needs no auth, assert env passed via a spy on `git`); a stderr containing the token is
      redacted; dry run without a key works → FAIL → implement → PASS → commit

### Task 12: hardening of the user units

**Files:** Modify `ops/systemd/*.service`; Test `tests/ops/test_units.py`

Every service gets `NoNewPrivileges=yes`, `RestrictSUIDSGID=yes`, `LockPersonality=yes`,
`RestrictRealtime=yes`, `RestrictNamespaces=yes`, `SystemCallArchitectures=native`,
`SystemCallFilter=@system-service`, `SystemCallErrorNumber=EPERM`, `MemoryDenyWriteExecute=yes`,
`UMask=0077`, `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK`; a comment block says
which options cannot work for user units on illouminus and why (AppArmor userns restriction), with
the follow-up (system units under a dedicated user with its own keys directory).

- [ ] test: every service has the set; no service carries a mount-namespace option (they would be
      silently ignored, or fail with 226) → FAIL → implement → PASS
- [ ] host check: `systemd-run --user` with the same properties runs `.venv/bin/apifacts version`, `gh --version`, `git` → ok

### Task 13: specs 05/08, ship PR-2, enable quorum

- [ ] spec 05 merge rule + token line; spec 08 token + hardening line; ruff + pytest green; PR; review;
      CI; merge; deploy; `systemctl --user cat agentfacts-quorum.service`;
      `ssh illouminus 'systemctl --user enable --now agentfacts-quorum.timer'`; one manual
      `systemctl --user start agentfacts-quorum.service`; journal shows no PR and no gh error.
- [ ] megabrain: `state_journal_append`, `state_task_update` on the sec card; remove the worktree.
