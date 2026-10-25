# 05 · Observations → quorum → probe → bot

**Done when:** `apifacts quorum run` turns a fixture set of observations into exactly the expected
`reported` fact drafts, schedules probes for the ones with a probe template, and `apifacts bot
publish` opens one PR containing the new YAML files with CI green; a fixture below quorum produces
nothing (tested).

## Quorum (hourly timer)

Group observations of the **current salt period** (Monday 00:00 UTC → now, at most 7 days; the salt and
the window coincide by decision 2026-10-20) by key `(service, method, path_template, error_hash)` (for
status-only signals: `(service, template, status)`). Pre-flight calls are never stored (`03`), so every
row carries a signal.

| Threshold | Value |
|-----------|-------|
| Distinct reporter networks (IPv4 /16, IPv6 /32, salted per period) | ≥ 3 |
| Distinct UA classes or SDK packages, counted only from networks with ≥ 2 observations in the period | ≥ 2 |
| Window | the current salt period (≤ 7 days, Monday–Sunday UTC) |
| Same group already a fact | refresh `evidence.observations`, no new draft |

The UA class and the SDK package are declared by the client itself, so they are the weaker factor:
a network's client counts toward it only from that network's second observation in the salt period
(in any group). One row from each of several fresh networks, each with its own User-Agent, buys no
second factor (D-093, 2026-10-25).

A group that meets quorum → `facts/<service>/<slug>.yaml` draft with `status: reported`,
`kind` inferred by rule (429 or rate-limit header → `rate_limit`; 2xx with empty-body fingerprint →
`silent_behavior`; 401/403 → `auth_quirk`; 410 or `Sunset` header → `deprecation`; else
`error_meaning`), `claim` generated from a **template per kind** (e.g. `error_meaning`: "{METHOD}
{template} returns HTTP {status} with "{error_string}"."), `fixes: [{action: none_known, reason_kind:
investigating}]`. No LLM: claims from templates only; a human or producer rewrites the claim in a PR
if they want prose.

Slug = `{status}-{first 6 words of normalized error, kebab}` deduplicated with `-2`, `-3`.

## Probe scheduling

If `probes/<service>/` has a probe whose `steps[].path` equals the group's template and whose
`assert[]` includes the signal (status or error string), it is marked due immediately (budget still
applies). Confirmation upgrades `reported` → `verified:server:<env>`. If no probe exists, the draft
stays `reported` and is listed in the weekly digest under "needs a probe" (an agent-hours item, no tap).

## Bot

- Runs after quorum (hourly). Collects new/changed files under `facts/`. A PR opens at once only for
  a new or deleted fact or a change beyond the evidence counters (status, claim, …), except quorum
  drafts (new `reported` facts from `observation_quorum`): each needs a human tap, so they gather
  in the checkout and go out as one PR a salt period — the first run that sees one notes its period
  in `bot-state.json` (a run that finds no draft held drops the note, so a draft that went out
  another way does not open next week's gate at once), the first run of a later period opens one
  PR with every draft gathered, and
  the Monday digest counts them (D-093: many networks pushing junk strings must not become a tap per
  string). Other new facts and status changes still go out at once. Counter-only
  changes (`last_confirmed`, `confirmations`, `stale_counter`, `vantages`, `observations`) go out as
  one PR a day, "facts: daily evidence refresh (<date>)", after `probe run --refresh-evidence`
  (incident 2026-10-24: a PR per counter refresh, 62 PRs in three days).
- One branch `bot/facts-<date>-<n>`, one PR, body = table of facts (id, kind, status, evidence), label
  `facts`. Never touches code paths.
- Merge: the PR auto-merges when CI (schema validation + pages build) is green **and** every fact in it
  is `verified:*` written by the bot. A PR with a `reported` fact (quorum drafts included) or a fact a
  human wrote opens without auto-merge, labelled `needs-review`, and waits for a human `[tap]`: an
  anonymous quorum never publishes on its own (sec card 2026-10-23, variant 1, D-089).
- Token: the bot's own fine-grained PAT, `agent-facts-bot` (this repo only, Contents + Pull requests),
  read by name from the keys directory; `gh` gets it as `GH_TOKEN`, git through an env-only credential
  helper. No token → the bot refuses; it never uses the host owner's `gh` login.
- Commit author `agent-facts-bot`, `Co-Authored-By` none; signed-off trailer with the runner's vantage.
- Kill switch (`04`) also stops the bot.

## Abuse controls

- Observations from a single reporter net never exceed 1,000 / day (silently dropped beyond).
- One signal group — (service, method, path template, status) — holds at most 200 distinct normalized
  error strings per salt period (Monday 00:00 UTC week), so many networks inventing strings inside
  their rate limits cannot grow the table without bound. A string already in the group always gets
  in; a new one past the cap evicts the least recent string seen only once (`evicted_template_cap`),
  and when every kept string has repeated it is dropped and counted (`dropped_template_cap`). The
  most frequent strings — the only ones that can reach a quorum — stay.
- A normalized error string that contains a URL outside the service's `hosts` + `doc_hosts`, or carries
  a prompt-injection marker (list in `03` step 7) → dropped and counted, never stored (the strings land
  on pages and in `check()` answers).
- Pages and `check()` answers only render the **normalized** string, inside a code span, never raw.
