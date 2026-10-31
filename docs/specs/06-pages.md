# 06 · Fact pages

**Done when:** `apifacts pages build` regenerates `pages/` deterministically (second run = no diff),
every fact has a page whose H1 is the vendor's error string verbatim (else the normalized string, else the
claim for kinds without a string), every service has an index, `pages/index.md` lists services, and a test checks that a page
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
# `Keys for idempotent requests can only be used with the same parameters they were first used with.`

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
Match signature (what `check()` matches): `keys for idempotent requests can only be used with the same parameters…`

`POST https://apifacts.dev/v0/check` with `{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"…"}}` · YAML: [facts/stripe/idempotency-key-reuse-different-params.yaml](../../facts/stripe/…)

---
Data: CC BY 4.0 · apifacts registry · This page is generated; edit the YAML, not the page.
```

Rules: error strings only inside code spans — the H1 is `signal.error_string` verbatim (decision 31.10:
agents search the message as they got it, case and digits intact), the normalized form stays below as
the match signature, error stubs are titled with it; a reporter's string is never shown raw (05); no vendor opinions; no security vulnerabilities (plan
§12.1 p.8); `stale` facts keep their page with a grey badge; `retracted` facts get a one-line page with
the reason; `reported` facts render with a yellow badge and "not yet reproduced by a probe".

## Publishing

Wave 1: committed to the repo, rendered by github.com (private until the repo goes public `[tap]`).

### HTML on the domain (decision 25.10)

The API process serves the same files as HTML on `apifacts.dev` (`apifacts/api/site.py`), so a
vendor or a developer opens a fact at the address the plugin prints, not a blob on GitHub. No landing
page, no marketing, no analytics, forms, scripts or web fonts: one inline stylesheet.

| Path | Source |
| --- | --- |
| `/` | `README.md` |
| `/registry` | `pages/index.md` |
| `/<service>/` (`/<service>` → 308) | `pages/<service>/index.md` |
| `/<service>/<slug>` | `pages/<service>/<slug>.md` (also `pages/errors/<hash>.md`) |
| `/llms.txt` | generated: what the registry is, the `/v0` endpoints, services, licenses, opt-out |
| `/robots.txt` | `Allow: /` for everyone, `Sitemap: https://apifacts.dev/sitemap.xml` |
| `/sitemap.xml` | every HTML page above, `lastmod` = last change of substance (below) |
| `/<INDEXNOW_KEY>.txt` | the IndexNow key (`apifacts/api/site.py`), public by design |

Markdown is rendered once at startup with markdown-it-py (CommonMark + tables, raw HTML off: every
string, error strings included, reaches the browser escaped), like the facts index — a new registry
needs a restart. Relative links are rewritten to these paths; a link to any other file of the repo
(probe, fact YAML, license) goes to its blob on GitHub. Responses carry a strong `ETag` and
`Cache-Control: public, max-age=300`; an unknown page is an HTML 404, while `/v0/...` keeps the JSON
error envelope. None of these routes is in `openapi.json`. The plugin and the CLI print
`https://apifacts.dev/<service>/<slug>`.

### Search engines (decision 31.10)

An agent searches the exact error string; Bing (ChatGPT search, many agent search APIs), Brave and
Exa must find the page. A fact page's `<title>` is `Stripe API 400 amount_too_small: <error string> ·
apifacts` (service, status, code, then the H1 text verbatim; clipped at a word past 160 characters)
and its `<meta name="description">` is the claim; a service index gets a title and a description
too. Both come from the facts index (`templates.head_title`, `head_description`, `service_head`),
not from the rendered markdown; a page the index does not know keeps its H1 as the title.

`lastmod` must not move when the nightly refresh only re-confirms a fact (every fact page changes
its `last confirmed` / `N confirmations` line every day). The site hashes each page's markdown
with those counters stripped (`templates.substantive`; a test bumps every volatile evidence field
and expects equal output) and remembers `{sha256, lastmod}` per path in
`var/sitemap-lastmod.json` (`APIFACTS_SITEMAP_STATE`): a page keeps its date while the hash holds,
a changed or new page is dated the day the API starts serving it. The fact's own dates were
rejected: no field records a hand-edited claim, a new sibling row or a template change.

`ops/indexnow.py` (timer `agentfacts-indexnow`, daily 05:00 Paris) reads the local
`/sitemap.xml`, POSTs the URLs whose `lastmod` moved since the last accepted submission — new
ones and removed ones included, the first run everything — to `api.indexnow.org` in one batch
with `keyLocation`, and records the answer in `var/indexnow.json`; a refusal is retried in full the
next day.
