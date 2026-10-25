# 09 · Work breakdown v0.1 (2026-10-20)

**Done when:** every package below is merged into `main` through its own PR with green CI, in the
dependency order given; W7 has the wave-1 services live in `facts/` with ≥ 10 facts each; W8 runs on
illouminus and the first Monday digest has arrived.

## Process for every package (the "как положено" part)

1. **One package = one session, one branch, one PR.** Branch names below. Start from `main`.
2. **Plan first:** the session reads the spec(s) listed, then writes its own bite-sized plan with the
   `writing-plans` skill into `docs/superpowers/plans/<date>-<package>.md` of the private repository apifacts-internal (tests first, exact files,
   exact commands). This file is the decomposition; the per-package plan is the engineer's.
3. **TDD:** failing test → minimal code → green → commit; `uv run pytest -q` and `uv run ruff check .`
   green locally before every push.
4. **PR ready at once**, self-review of the local diff with `/code-review`, every finding fixed in the
   same PR (including small ones), CI green, merge. `ccd_pr` bind + `set_monitor {auto_fix: true}`.
5. **Blast-radius for this repo** (stop and ask Edouard before code): ingestion rules and thresholds
   (`03`, `05`), anything that reads `~/.private_keys`, `ops/publish-policy.yaml`, making the repo public,
   paid resources. Everything else the session decides alone (decision 2026-10-20).
6. **Evidence with "done":** the test command and its output, the PR URL, and for W8 the timer status.
7. **State:** a journal line in megabrain `projects/agent-facts.md` per merged package.

## Packages

| Pkg | Name | Branch | Specs | Depends on | Estimate* | Measured (opus session, worktree → merge) |
|-----|------|--------|-------|------------|-----------|-------------------------------------------|
| W0 | Scaffold + CI + public README | `feat/w0-scaffold` | 00 | — | 0.5–1 h | 11 min (PR #1) |
| W1 | Schemas + validator CLI | `feat/w1-schemas` | 01, 02 | W0 | 1–2 h | 18 min (PR #2) |
| W2 | Probe runner | `feat/w2-probe-runner` | 04, 01 | W1 | 2–3 h | 43 min (PR #6) |
| W3 | `check()` API + ingestion | `feat/w3-check-api` | 03, 01 | W1 | 2–3 h | ~1 h (PR #4, 463 tests) |
| W4 | Quorum + bot | `feat/w4-quorum-bot` | 05 | W2, W3, answers to the 7 ingestion questions | 2 h | — |
| W5 | Pages generator | `feat/w5-pages` | 06 | W1 | 1–2 h | 18 min (PR #3) |
| W6 | pytest plugin + CLI `check` | `feat/w6-pytest-plugin` | 07, 03 | W1 (W3 mocked) | 1–2 h | 35 min (PR #5) |
| W7 | Seed content, wave 1 (10 services × ≥ 10 facts) | `content/w7-wave1-<service>` (one PR per service) | 01, 04, research doc | W1, W2 | 3–5 h | keyless 3 services: ~1.5 h (PRs #7–#9, 53 facts) |
| W8 | Ops on illouminus + digest + state | `feat/w8-ops` | 08 | W2–W6 | 2 h | — |
| W9 | jest plugin, MCP server, client sandbox (`verified:client`) | `feat/w9-*` | 07 | W3, W6 | 3 h | — |

\* the 2026-10-20 estimates were 3–5× too high for an opus session with a written spec; W4/W8/W9 should expect 30–60 min each. Calibration lives here, not in prose.

### Order and parallelism

```
W0 ──▶ W1 ──┬──▶ W2 ──┐
            ├──▶ W3 ──┼──▶ W4 ──┐
            ├──▶ W5   │         ├──▶ W8 ──▶ (public repo [tap]) ──▶ W9
            └──▶ W6   │         │
                      └──▶ W7 ──┘   (W7 keyless services can start right after W2;
                                     keyed services wait for Edouard's keys [tap])
```

W2, W3, W5, W6 run in parallel sessions (own worktrees, no shared files: `apifacts/probe`,
`apifacts/api`, `apifacts/pages`, `plugins/pytest`). W7 is content, one PR per service, can be
spread over several sessions.

## W0 · Scaffold

**Files:** `pyproject.toml` (package `apifacts`, Python 3.12, deps: pydantic>=2, pyyaml, ruamel.yaml,
httpx, typer, jsonschema, fastapi, uvicorn; dev: pytest, pytest-httpserver, ruff), `apifacts/__init__.py`,
`apifacts/cli.py` (typer app with `version`), `tests/test_cli.py`, `.github/workflows/ci.yml`
(uv sync, ruff, pytest, `apifacts validate` once W1 exists), `README.md` (public-facing English:
what/why/how to call `check()`/license/contributing), `CONTRIBUTING.md`, `CODEOWNERS` (`facts/` → bot +
Edouard; `services/<x>` producers later), `.editorconfig`.
**Done when:** `uv run apifacts version` prints the version; CI runs on a PR in < 2 min and is green;
`README.md` explains the registry in ≤ 400 words with one curl example.

## W1 · Schemas + validator

**Files:** `schema/fact.schema.json`, `schema/service.schema.json`, `schema/probe.schema.json`,
`schema/observation.schema.json`, `schema/fix.schema.json`; `apifacts/schema/models.py` (pydantic
mirrors), `apifacts/schema/validate.py`, `apifacts/fixes/templates.py` (render per action), CLI
`apifacts validate [paths]` and `apifacts render-fix <json>`; fixtures `tests/fixtures/valid/` (one
service, one fact, one probe) and `tests/fixtures/invalid/` (free-text fix, unregistered path template,
prod probe with POST, claim > 300 chars, unknown kind); tests per fixture and per fix action (golden
sentence).
**Done when:** criteria in `01` and `02`; validator exit codes: 0 ok, 1 invalid with
`file:line: code message`, 2 usage.

## W2 · Probe runner

**Files:** `apifacts/probe/{loader,templating,http,assertions,budget,keys,redact,runner,results}.py`,
CLI `apifacts probe run [--due|--all] [--max N] [--vantage NAME] [--dry-run]`, `apifacts probe
list`; tests with `pytest-httpserver` for every step and assertion kind, budget/kill-switch tests,
redaction test (fake key never appears in `results.jsonl`), "different env never refutes" test.
**Done when:** criteria in `04`.

## W3 · `check()` API

**Files:** `apifacts/api/{app,models,match,normalize,store,ratelimit,facts_index}.py`, sqlite schema
`apifacts/api/schema.sql`, `docs/specs/openapi-v0.json` (exported by a test, diff-checked),
`tests/api/test_check_contract.py`, `tests/api/test_normalize.py` (digits, uuids, emails, urls,
truncation, secret-shaped), `tests/api/test_default_deny.py` (unregistered target: answer yes, row no).
**Done when:** criteria in `03`; `uvicorn apifacts.api.app:app` serves `/healthz`.

## W4 · Quorum + bot

**Files:** `apifacts/quorum/{group,rules,draft}.py`, `apifacts/bot/{collect,pr}.py` (uses `gh`),
CLI `apifacts quorum run [--since 7d] [--dry-run]`, `apifacts bot publish [--dry-run]`; fixtures of
observations above/below quorum; tests for kind inference, slug generation, dedup, prompt-injection
drop rule, PR body rendering (no network: `gh` mocked).
**Done when:** criteria in `05`.

## W5 · Pages

**Files:** `apifacts/pages/{build,templates,errors_index}.py`, CLI `apifacts pages build [--out
pages/]`, golden tests (`tests/pages/golden/*.md`), determinism test (build twice, no diff), CI step that
fails if `pages/` is not up to date with `facts/`.
**Done when:** criteria in `06`.

## W6 · pytest plugin + CLI check

**Files:** `plugins/pytest/pyproject.toml` (package `apifacts-pytest`, entry point `pytest11`),
`plugins/pytest/apifacts_pytest/{plugin,extract,client,render}.py`, tests using `pytester` and a fake
`check()` server; `apifacts/cli_check.py` for `apifacts check <url> [--status N --body FILE]`.
**Done when:** criteria in `07` (wave 1 part).

## W7 · Seed content, wave 1

**Input:** `docs/research/seed-100-2026-10-20.md` (private repository apifacts-internal) (wave-1 list, approved by Edouard `[tap]`), vendor docs,
the gotchas list (Gemini, unverified) as hints only.
**Per service (one PR):** `services/<s>.yaml` (hosts, templates, signal_fields, dimensions, auth key
name, tos source), `probes/<s>/*.yaml` (≥ 5 declarative probes, prod ones read-only), `facts/<s>/*.yaml`
(≥ 10 facts, each `verified:*` by a probe run on illouminus or `official` with a doc URL; `reported`
not allowed in the seed), pages regenerated.
**Keys:** keyless services need nothing; keyed ones wait for `~/.private_keys/<name>.key` placed by
Edouard with `keyput` `[tap per service, ~5 min each]`. Start with the keyless ones.
**Done when:** `apifacts validate` green, `apifacts probe run --all` on illouminus confirms every
`verified:*` fact at least once (log attached to the PR), pages built.

## W8 · Ops

**Files:** `ops/systemd/agentfacts-{probe,quorum,digest}.{service,timer}`, `ops/deploy.sh`
(vps-auto-deploy pattern), `ops/digest.py` (+ `send_telegram` question class with one tap),
`ops/publish-policy.yaml` (templates for issue/SO answer, vendor allowlist — approved by Edouard
`[tap once]`), `ops/KILL` handling, `Caddyfile` snippet for `apifacts.dev`, state journal hook.
**Done when:** criteria in `08`; `systemctl --user list-timers` shows the three timers; `/healthz` over
HTTPS; a dry-run digest delivered.

## W9 · Wave 2 (later)

jest/vitest reporter, MCP server with one tool, client sandbox container that reproduces SDK-level
facts (`verified:client`), GitHub Pages + `llms.txt` + sitemap, registry listings. Planned after W8 and
the week-8 gauge (`README` → Замеры и пороги).

## What Edouard does, in order

1. Approve the wave-1 list (one message).
2. Place keys for the keyed wave-1 services with `keyput` as W7 reaches them (~5 min each).
3. DNS record `apifacts.dev` → illouminus (W8).
4. Approve `ops/publish-policy.yaml` once (W8).
5. Make the repo public when W7 is in (one click).
Everything else is agent work.
