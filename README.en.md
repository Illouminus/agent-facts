# apifacts

**A verified changelog of reality for AI agents.** An open registry of typed, dated facts about what
third-party machine interfaces (HTTP APIs, SDK packages, CLIs) actually do today, as opposed to what
their docs say.

## Why

Interfaces change, docs lag, and nobody tells the agent. Every session pays tokens to rediscover the
same traps: a `200` with an empty array instead of a `429`, a rate limit reported as `status: 0` in the
body, an SDK release that silently dropped a field. Documentation tools answer "give me the right docs";
apifacts answers "the docs are wrong about this endpoint right now, here is the verified difference".

## Install

```bash
pip install apifacts-pytest   # pytest plugin: a test failing on an HTTP error prints the known facts
uvx apifacts check https://api.stripe.com/v1/charges -X GET --status 401   # CLI (and library)
```

Both packages are on PyPI, carry the same version and ship together from one tag
([release](ops/README.md#release-to-pypi)). The plugin sends nothing until a test fails.

## How a fact is verified

- One fact per YAML file in `facts/<service>/`, with a kind (`error_meaning`, `rate_limit`,
  `breaking_change`, ...), the exact error signal, a one-sentence claim, dimensions (`env`, `plan`,
  `region`, `account_state`) and evidence.
- Truth comes only from **deterministic probes**: declarative HTTP steps and assertions that our runner
  executes on a schedule. No language model is called anywhere in the verification path.
- Fixes are **data, not advice**: members of a closed vocabulary with typed parameters (no free text, no
  shell, no foreign URLs), rendered to one English sentence by us.
- A probe in another environment never refutes a fact; it adds a dimension.

## Calling `check()`

One endpoint answers and learns at the same time: the request is the contribution. Send the target and,
optionally, the error you got; receive matching facts with typed fixes and what the probes observe. If
the target matches a registered template, a normalized observation is stored (no bodies, headers, query
strings or raw IPs).

```bash
curl -s https://apifacts.dev/v0/check \
  -H 'Content-Type: application/json' \
  -d '{"target": {"method": "POST", "url": "https://api.stripe.com/v1/payment_intents"},
       "error": {"status": 400, "body_excerpt": "Keys for idempotent requests can only be used with the same parameters they were first used with."}}'
```

The response is never empty: `facts`, `observed`, and an `unknown.reason` when nothing matches.

## Status

The API is live at https://apifacts.dev (`/v0/check`, `/v0/services`, `/openapi.json`, `/healthz`;
`facts.baillot.dev` is a legacy alias). The registry covers the services and facts listed in
[`pages/index.md`](pages/index.md), each fact page showing how it was established. Design contracts
live in [`docs/specs/`](docs/specs/README.md).

Running your own copy: the API reads `facts/` and `services/` once, at startup, so after a `git pull`
restart it; [`ops/deploy.sh`](ops/README.md#deploy) checks out, syncs and restarts in one step.

## Contributing

Calling `check()` is contributing. Pull requests are for humans and API producers: see
[CONTRIBUTING.md](CONTRIBUTING.md). Producer signatures are always free.

## License

Code: [MIT](LICENSE). Data (`facts/` and the generated fact pages): [CC BY 4.0](LICENSE-DATA).
