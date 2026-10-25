# 06 · Fact pages

**Done when:** `apifacts pages build` regenerates `pages/` deterministically (second run = no diff),
every fact has a page whose H1 is the exact normalized error string (or the claim for kinds without a
string), every service has an index, `pages/index.md` lists services, and a test checks that a page
contains the fix sentences, the status badge, the first-seen/last-confirmed dates and the CC BY 4.0 line.

## Why pages first

An agent that hits an error searches the exact string. Vendor-specific strings have little competition;
`github.com` pages are indexed within days. Pages cost zero tokens until the moment of failure (plan
§18, Argon's token-tax point).

## Layout

```
pages/
  index.md                      # services, counts, registry version
  <service>/index.md            # facts by kind, with status badges
  <service>/<slug>.md           # one fact
  errors/<error-hash-prefix>.md # redirect-style stub: the normalized string → the fact page (search bait)
```

## Fact page template

```markdown
# `keys for idempotent requests can only be used with the same parameters…`

**Stripe · POST /v1/payment_intents · HTTP 400 `idempotency_error`**
Status: ✅ verified:server:sandbox · first seen 2026-10-22 · last confirmed 2026-10-29 · 7 confirmations from 1 vantage

> Reusing an Idempotency-Key with a different request body returns HTTP 400 idempotency_error for 24 hours after the first request.

## What to do
1. Send header `Idempotency-Key` = new UUID per distinct request.

## Dimensions
env: sandbox · plan: any · region: any · account_state: any · prod: not probed (POST is write-only there)

## Evidence
Probe `af:stripe:probe:idempotency-key-reuse` (declarative, [source](../../probes/stripe/idempotency-key-reuse.yaml)) · official doc: https://docs.stripe.com/api/idempotent_requests
Observations: 12 distinct networks in the last 30 days.

## Machine access
`POST https://apifacts.dev/v0/check` with `{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"…"}}` · YAML: [facts/stripe/idempotency-key-reuse-different-params.yaml](../../facts/stripe/…)

---
Data: CC BY 4.0 · apifacts registry · This page is generated; edit the YAML, not the page.
```

Rules: normalized strings only, inside code spans; no vendor opinions; no security vulnerabilities (plan
§12.1 p.8); `stale` facts keep their page with a grey badge; `retracted` facts get a one-line page with
the reason; `reported` facts render with a yellow badge and "not yet reproduced by a probe".

## Publishing

Wave 1: committed to the repo, rendered by github.com (private until the repo goes public `[tap]`).
Wave 2: GitHub Pages from `pages/` with a sitemap, `llms.txt` at the root listing services and the
`check()` endpoint, and `robots.txt` allowing all.
