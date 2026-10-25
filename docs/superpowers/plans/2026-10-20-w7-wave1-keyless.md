# W7 · Seed content, wave 1 — keyless services (github, pypi, solana) · 2026-10-20

Spec: `docs/specs/09-work-breakdown.md` (W7), `01`, `02`, `04`, `06`. One PR per service, in this
order: github → pypi → solana. Branches `content/w7-wave1-<service>` from a fresh `origin/main`.

## Per service

1. Measure first, by hand and sparingly (GitHub anonymous = 60 requests/hour per IP): which
   behaviours are reachable keyless with `GET`/`HEAD` (prod probes are read-only) and stable enough
   to re-run every budget window.
2. `services/<s>.yaml`: hosts, only the templates facts and probes use, `signal_fields`,
   `account_state: [anonymous]`, `auth: none`, ToS source, `probe_budget` (github 1800 s).
3. `probes/<s>/*.yaml` (≥ 5): one probe per group of facts that must fail together; a fragile
   assertion (schema fingerprint) gets its own probe so its drift never stales unrelated facts.
4. `facts/<s>/*.yaml` (≥ 10): `verified:server:prod` only when a probe in this PR asserts the
   signal; otherwise `official` with the vendor doc URL and the claim taken from the doc.
   `signal.normalized` = `apifacts.api.normalize.normalize(error_string)`. No `reported`.
5. `uv run apifacts probe run --all --vantage mac-dev` → every probe passes and every verified
   fact gets `confirmations: 1`; `first_seen` = the first confirmation; log goes into the PR body.
6. `uv run apifacts validate`, `uv run apifacts pages build`, `uv run pytest -q`, `ruff check`.
7. PR ready → `/code-review` → fix all findings → CI green → squash merge.

## Solana only

Solana RPC is `POST` + JSON-RPC body, which the prod read-only rule refuses. A separate small commit
adds an explicit allowlist of read-only JSON-RPC methods to the service registration and lets a
prod probe `POST` only a JSON-RPC 2.0 body whose `method` is on that list (validator, model check
and runner re-check share `http_step_violations`), with tests.

## Lessons kept for later waves

- GitHub's anonymous `GET /repos/{owner}/{repo}` is publicly cached for 60 s and `Vary` omits
  `X-GitHub-Api-Version`: a probe comparing API versions must use a cache-busting query parameter
  (`cb: "{{run_uuid}}"`), or it measures the cache, not the version (first run of
  `repo-api-version-2026` failed exactly this way).
