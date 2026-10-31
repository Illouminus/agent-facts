# apifacts scan — GitHub Action

When a CI step fails on a third-party API error, this action puts what
[apifacts](https://apifacts.dev) knows about that error where a coding agent (Copilot, Claude Code,
Devin, …) looks while fixing the build: the step's log, a warning annotation on the run and the PR,
and the job summary.

It runs `apifacts scan` over the step's output: failed HTTP calls printed by python `requests` and
`httpx` (and the OpenAI/Anthropic SDK logs built on it), stripe-python's log, the `gh` CLI, axios, ky,
ofetch and `curl -f`. Only hosts in the registry are asked about; query strings, headers and request
bodies never leave the runner, and error bodies are redacted before they do.

## Wrap the command

```yaml
- uses: Illouminus/apifacts/action@v0
  with:
    run: pytest -q
```

The command runs with `bash -eo pipefail`, its output is shown as usual, and the step ends with the
command's own exit code: a green command stays green, a red one stays red. The scan only runs when
the command fails, so a green build installs nothing.

## Scan the log of a failed step

```yaml
- name: Tests
  shell: bash          # pipefail: without it `| tee` hides the failure
  run: npm test 2>&1 | tee test.log

- uses: Illouminus/apifacts/action@v0
  if: failure()
  with:
    log-file: test.log
```

In this mode the action always succeeds; the failure stays on the step that failed.

## Inputs

| Input | Default | |
|-------|---------|---|
| `run` | | Shell command to run (bash). |
| `log-file` | | A log file to scan instead. |
| `offline` | `false` | Answer from the fact snapshot packaged in the release; nothing is sent. |
| `version` | the current release | apifacts version from PyPI. |

## What the agent sees

In the log and the job summary, one section per failed call, as `apifacts check` prints it:

```
POST api.stripe.com/v1/payment_intents → 400
✅ verified:server:prod · Reusing an Idempotency-Key with a different request body returns HTTP 400 …
   fix: Set parameter Idempotency-Key to new UUID per distinct request
   https://apifacts.dev/stripe/idempotency-key-reuse-different-params
```

A warning annotation is added only when the registry has a fact for that exact status.

## How it runs

One bash step (Git Bash on Windows). `apifacts` is started with `uvx` when the runner has `uv`,
otherwise with `pipx run`, which ubuntu-, macos- and windows-latest ship with Python ≥ 3.12; on a
self-hosted runner with neither, the scan is skipped with a notice. Nothing in the action can fail
the step: an unreachable registry, an install error or a crash in the scan is a `::notice`.
`APIFACTS_DISABLE=1` sends nothing; `APIFACTS_ENDPOINT` points at another registry.

When the log does not say the method (`requests`, `httpx` and `gh` errors do not), the call is asked
without reporting the error, and only when the registry knows a single method for that path;
otherwise the section names the `apifacts check … -X <METHOD>` command to run. A guessed method is
never sent.
