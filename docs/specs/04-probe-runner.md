# 04 · Probe runner v0.1

**Done when:** `agentfacts probe run --due` executes every due probe under `probes/`, writes one line per
step to `results.jsonl`, updates `evidence` of facts that reference the probe (confirm / stale counter),
respects budgets and the kill switch, injects keys only by name, and a test suite with a local mock
HTTP server covers every step kind and every assertion kind.

## Declarative probes only

A probe is YAML (`01`): `steps[]` of `do: http` (and `do: sleep`) with templated values, and `assert[]`.
No code per probe. If a behaviour cannot be expressed declaratively it is not probed in wave 1 and the
fact stays `reported` or `official`.

| Step field | Meaning |
|-----------|---------|
| `method`, `path`, `query`, `form`, `json`, `headers` | request; `path` must be a registered template instance |
| `{{run_uuid}}`, `{{now_rfc3339}}`, `{{step[1].json.id}}` | templating; only these three forms |
| `auth: service` (default) | adds the service's auth header from the injected key |
| `expect_rate_limit: true` | marks a step allowed to return 429 without failing the run |

| Assertion (every entry carries `step: N`, 1-based) | Shape (as in the spec 01 example and `schema/probe.schema.json`) |
|-----------|--------|
| status | `{step: 2, status: 400}` |
| header | `{step: 1, header: Retry-After, present: true}` / `equals: …` / `matches: <regex>` |
| json_path | `{step: 2, json_path: $.error.code, equals: idempotency_error}` / `contains: …` / `exists: true` |
| body_contains | `{step: 1, body_contains: "same parameters"}` |
| latency_ms | `{step: 1, latency_ms: {lt: 2000}}` |
| schema_fingerprint | `{step: 1, schema_fingerprint: <sha256 of sorted top-level keys>}` (drift detection) |

## Execution

- Due = `now − last_run ≥ service.probe_budget.per_template_seconds` and not killed; max N probes per tick.
- Each run records `{probe_id, vantage, selection, env, started, steps:[{status, latency_ms,
  headers(whitelist), body_fingerprint, error_string(normalized)}], asserts:[{ok, detail}]}`;
  `selection` is `due` (the tick honoured budgets) or `all` (`probe run --all`, budgets skipped), so
  the digest counts only `due` pairs closer than the budget as violations (added 20.10.2026).
- Outcome → facts referencing the probe: all asserts ok → `last_confirmed`, `confirmations += 1`,
  `stale_counter = 0`; any assert failed → `stale_counter += 1`; counter ≥ 3 → status `stale`
  (previous status kept in `history`). A failure in a **different env** than the fact's dimension never
  touches the fact (`01` rule).
- Counters live in `var/evidence-pending.sqlite`; a tick writes the fact YAML only on a status change
  (verified, stale, restored) or a first confirmation from a new vantage. The daily
  `probe run --refresh-evidence` (03:00 Europe/Paris) writes the counters once. Incident 2026-10-24:
  counters written every 15 min became 62 bot PRs, 137 CI runs and 62 deploys in three days.
- Unexpected 429, or a 403 with `X-RateLimit-Remaining: 0` (GitHub's spent limit, shared with other
  clients of the IP) on a step that does not assert 403, is `error`, never evidence.
- Side effects: probes may only create objects in `env: sandbox`; a probe with `env: prod` must be
  read-only: `GET`/`HEAD`, or a `POST` whose body is one JSON-RPC call to a method listed in the
  service's `surfaces.http.jsonrpc.read_methods` (added by W7 for Solana, PR #9) — enforced by the validator.

## Keys and secrets

- `services/*.yaml::auth.key_name` → the runner reads `~/.private_keys/<key_name>.key` at start; nothing
  else reads it. Missing key → the service's keyed probes are skipped with `skipped:no_key`, never an error.
- Redaction filter on every string before it reaches `results.jsonl`, logs or facts: the key values
  themselves, `sk_[a-z]+_[A-Za-z0-9]{8,}`, `Bearer [A-Za-z0-9._-]{16,}`, generic 32+ hex/base64 runs.
- A test injects a fake key and asserts it appears in no output file.

## Vantage points

Wave 1: `illouminus` only. Wave 3: `prod-vps` and `freebox` (residential, via the existing WireGuard
netns), each runner tagging its vantage; a fact's `evidence.vantages` lists where it reproduced.

## Kill switch and budgets

`ops/KILL` file or `AGENTFACTS_KILL=1` → the runner exits before the first request. Per-service
`probe_budget`; global cap `max_requests_per_tick` (default 50). Honest `User-Agent:
agent-facts-probe/<version> (+https://github.com/Illouminus/agent-facts; opt-out: <email>)`.

## Design parameters

| Parameter | Value |
|-----------|-------|
| Tick | every 15 min (systemd timer) |
| Per-template budget | 300 s default; per service override |
| Max requests per tick | 50 |
| Request timeout | 20 s |
| Stale after | 3 failed runs |
