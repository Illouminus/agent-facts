# 01 · Fact schema v0.1

**Done when:** `schema/fact.schema.json`, `schema/service.schema.json`, `schema/probe.schema.json`,
`schema/observation.schema.json` exist, `agentfacts validate` passes on every file under `services/`,
`facts/`, `probes/`, and rejects the fixtures in `tests/fixtures/invalid/` with the expected error codes.

## Fact (one per file, `facts/<service>/<slug>.yaml`)

```yaml
id: af:stripe:idempotency-key-reuse-different-params      # stable; af:<service>:<slug>
service: stripe                                            # key of services/stripe.yaml
kind: error_meaning                                        # enum below
target:
  surface: http                                            # http | sdk | cli
  method: POST
  path_template: /v1/payment_intents                       # from the service's registered templates
  sdk: {package: stripe, ecosystem: pypi, versions: ">=7,<13"}   # optional, when surface=sdk
signal:                                                    # what the agent observes
  status: 400
  error_code: idempotency_error                            # vendor code if any
  error_string: "Keys for idempotent requests can only be used with the same parameters they were first used with."
  normalized: "keys for idempotent requests can only be used with the same parameters they were first used with"
claim: >                                                   # ONE sentence, declarative, no advice
  Reusing an Idempotency-Key with a different request body returns HTTP 400 idempotency_error
  for 24 hours after the first request.
dimensions:
  env: prod                                                # prod | sandbox
  plan: any                                                # vendor plan name or any
  region: any
  account_state: any                                       # enum defined per service
fixes:                                                     # typed only, see 02-fix-vocabulary.md
  - {action: set_param, name: Idempotency-Key, value_source: new_uuid_per_distinct_request}
status: verified:server:prod                               # see table
evidence:
  probe: af:stripe:probe:idempotency-key-reuse             # probes/stripe/idempotency-key-reuse.yaml
  first_seen: 2026-10-22T09:14:00Z
  last_confirmed: 2026-10-22T09:14:00Z
  confirmations: 1
  vantages: [illouminus]
  official_url: https://docs.stripe.com/api/idempotent_requests    # optional; status official needs it
  observations: 0                                          # distinct reporter networks that hit this
provenance:
  source: probe | observation_quorum | producer | manual
  author: bot | producer:<org> | human:<handle>
  created: 2026-10-22
  history: [{date: 2026-10-22, change: created, by: bot}]
```

### Enumerations

| Field | Values |
|-------|--------|
| `kind` | `error_meaning`, `rate_limit`, `breaking_change`, `silent_behavior`, `auth_quirk`, `pagination`, `sandbox_divergence`, `deprecation`, `availability`, `schema_drift`, `latency_profile` |
| `status` | `verified:server:prod`, `verified:server:sandbox`, `verified:client`, `reported`, `official`, `stale`, `retracted` |
| `target.surface` | `http`, `sdk`, `cli` |
| `dimensions.env` | `prod`, `sandbox` |
| `provenance.source` | `probe`, `observation_quorum`, `producer`, `manual` |

### Status rules

| Status | Set when | Demoted when |
|--------|----------|--------------|
| `verified:server:prod` | a probe against prod reproduced the signal | 3 consecutive probe runs fail to reproduce → `stale` |
| `verified:server:sandbox` | same, against sandbox | same |
| `verified:client` | reproduced in the SDK sandbox container (W9) | same |
| `reported` | quorum met (`05`), no probe yet | 30 days without quorum refresh → removed from pages (kept in git) |
| `official` | producer PR or vendor doc URL + probe agreement | doc URL 404 for 7 days → `stale` |
| `stale` | see above; never means refuted | a reproducing probe restores the previous status |
| `retracted` | human or producer decision with reason | never |

A probe with a different `env`/`account_state` than the fact creates a **new dimension row** (a sibling
fact with the same slug and a `dimensions` suffix), it never changes the original's status.

## Service registration (`services/<service>.yaml`)

```yaml
key: stripe
name: Stripe
hosts: [api.stripe.com]
surfaces:
  http:
    base_url: https://api.stripe.com
    templates:                                   # the ONLY paths check() will store observations for
      - {method: POST, path: /v1/payment_intents}
      - {method: GET,  path: /v1/customers/{id}}
    signal_fields: [status, error.code, error.type, error.message, retry-after, stripe-version]  # whitelist
  sdk:
    - {ecosystem: pypi, package: stripe}
    - {ecosystem: npm, package: stripe}
dimensions:
  env: {prod: https://api.stripe.com, sandbox: https://api.stripe.com}     # same host, test keys
  account_state: [active, restricted, test_mode]
auth:
  kind: bearer
  key_name: stripe-test                           # ~/.private_keys/stripe-test.key on the runner only
  env: sandbox                                    # which env this key reaches
tos:
  automated_access: allowed
  publish_measurements: allowed
  source: https://stripe.com/legal/ssa
probe_budget: {per_template_seconds: 300}
```

## Probe (`probes/<service>/<slug>.yaml`) — see `04-probe-runner.md` for execution

```yaml
id: af:stripe:probe:idempotency-key-reuse
service: stripe
env: sandbox
steps:
  - {do: http, method: POST, path: /v1/payment_intents, form: {amount: 100, currency: usd}, headers: {Idempotency-Key: "{{run_uuid}}"}}
  - {do: http, method: POST, path: /v1/payment_intents, form: {amount: 200, currency: usd}, headers: {Idempotency-Key: "{{run_uuid}}"}}
assert:
  - {step: 2, status: 400}
  - {step: 2, json_path: $.error.code, equals: idempotency_error}
  - {step: 2, json_path: $.error.message, contains: "same parameters"}
```

## Observation (`observations.sqlite`, never in git)

`id, received_at, service, method, path_template, status, error_hash, normalized_error (≤ 512 chars),
reporter_net (/16 hashed with daily salt), reporter_ua_class, sdk_package, sdk_version, env_guess,
vantage_country`. No bodies, headers, query strings or raw IPs are ever stored (`03`).

## Design parameters

| Parameter | Value |
|-----------|-------|
| Max `claim` length | 300 chars |
| Max `error_string` stored | 512 chars |
| Stale after | 3 consecutive non-reproductions |
| Reported expiry | 30 days without quorum refresh |
