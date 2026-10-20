# 05 · Observations → quorum → probe → bot

**Done when:** `agentfacts quorum run` turns a fixture set of observations into exactly the expected
`reported` fact drafts, schedules probes for the ones with a probe template, and `agentfacts bot
publish` opens one PR containing the new YAML files with CI green; a fixture below quorum produces
nothing (tested).

## Quorum (hourly timer)

Group observations from the last 7 days by key `(service, method, path_template, error_hash)` (for
status-only signals: `(service, template, status)`).

| Threshold | Value |
|-----------|-------|
| Distinct reporter networks (/16, salted) | ≥ 3 |
| Distinct UA classes or SDK packages | ≥ 2 |
| Window | 7 days |
| Same group already a fact | refresh `evidence.observations`, no new draft |

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

- Runs after quorum and after each runner tick. Collects new/changed files under `facts/`.
- One branch `bot/facts-<date>-<n>`, one PR, body = table of facts (id, kind, status, evidence), label
  `facts`. Never touches code paths.
- Merge: the PR auto-merges when CI (schema validation + pages build) is green **and** every fact in it
  is `verified:*` or `reported` from quorum. Facts touched by a human PR require a human review `[tap]`.
- Commit author `agent-facts-bot`, `Co-Authored-By` none; signed-off trailer with the runner's vantage.
- Kill switch (`04`) also stops the bot.

## Abuse controls

- Observations from a single reporter net never exceed 1,000 / day (silently dropped beyond).
- A normalized error string that contains a URL outside the service's hosts, or looks like a prompt
  ("ignore previous", "system:", "assistant:") → dropped and counted, never stored (prompt-injection
  surface: the strings land on pages and in `check()` answers).
- Pages and `check()` answers only render the **normalized** string, inside a code span, never raw.
