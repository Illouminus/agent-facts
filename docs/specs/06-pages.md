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

## Example
What probe [`af:stripe:probe:idempotency-key-reuse`](../../probes/…) sends (sandbox) and what it checks …
Step 1 → HTTP 200: ```http POST https://api.stripe.com/v1/payment_intents / Authorization: Bearer <key> / Idempotency-Key: <run_uuid> / amount=100&currency=usd```
Step 2 → HTTP 400: ``` … amount=200 … ```
Response (only what the probe asserts; other fields omitted): ```http HTTP 400 {"error": {"type": "idempotency_error", "message": "Keys for …"}}```

## In your code
| SDK | Raises | Check |
| Python `stripe` | `stripe.IdempotencyError` | `e.http_status == 400` · `e.error.type == "idempotency_error"` |
| Node `stripe` | `Stripe.errors.StripeIdempotencyError` | `err.statusCode === 400` · `err.rawType === "idempotency_error"` |
Read from the SDK source: stripe 16.1.0: stripe/_api_requestor.py specific_v1_api_error …
Fix 1: ```python headers["Idempotency-Key"] = str(uuid.uuid4())  # a new value per distinct request…```

## Dimensions
env: sandbox · plan: any · region: any · account_state: any · prod: not probed (POST is write-only there)

## Evidence
Probe `af:stripe:probe:idempotency-key-reuse` (declarative, [source](../../probes/stripe/idempotency-key-reuse.yaml)) · official doc: https://docs.stripe.com/api/idempotent_requests
Observations: 12 distinct networks in the last 30 days.

## Related errors
- [`Keys for idempotent requests can only be used for the same endpoint …`](idempotency-key-other-endpoint.md) · POST /v1/payment_intents · HTTP 400 `idempotency_error`

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

### Article sections (decision 31.10)

A page should be the best answer to a search for its error string, for an agent and a human, with
nothing on it that the registry does not hold: no generated prose, no invented body. Each section is
omitted when its data is missing.

- **Example** (`apifacts/pages/example.py`): the fact's evidence probe replayed as text — every http
  step up to the one the fact is about (the last step asserting the fact's status, else the last
  asserted step), with method, URL on the env's base URL, query, probe headers and form/JSON body;
  templating shown as `<run_uuid>`, credentials only as where they go (`Authorization: Bearer <key>`,
  `x-goog-api-key: <key>`, `/bot<key>`, `?key=<key>`); every string passes the runner's strict
  redaction. The response shows the asserted status, the asserted headers, and a JSON excerpt built
  from the `json_path` assertions only: `equals` values verbatim, `contains` as the fact's recorded
  error string when that string holds the substring, else `…substring…`, `exists` as `…`; paths that
  cannot be placed without inventing array elements are listed as `path = value`. At most 8 fields.
- **In your code** (`apifacts/pages/sdk.py`, data in `apifacts/pages/sdk_errors.yaml`): for an error
  (status ≥ 400), the exception each mapped SDK raises and the attributes that carry status and code.
  The mapping is hand-kept data, each entry read from the SDK's published source at the version it
  names (`verified`, printed on the page); rules mirror the SDK's own first-match order and test only
  what a fact records (status, error_code, path template, error string). A rule that depends on
  something the fact does not record (a header, an unknown message) stops at the SDK's catch-all
  class, which is right whatever the SDK picks. Community SDKs are marked `(community)`. Below the
  table, typed fixes as code, one template per action (spec 02): `set_header`, `set_param`,
  `remove_param`, `use_endpoint`, `retry_after_header`, `backoff_exponential`, `encode_as`,
  `pin_sdk_version`, `upgrade_sdk`; the others (`none_known`, `request_scope`, `paginate_with`, …)
  need judgement and get no snippet. Account values become `YOUR_<SETTING>`. Snippets are pasted and
  run: registry values enter them only as JSON string literals, and a path becomes an f-string only
  when every brace is a `{identifier}` slot (else a plain string; tested with hostile templates).
- **Related errors** (`build.related`): other published error facts (status ≥ 400) of the same
  service with the same status or the same method + path template — both first, then same status,
  then same endpoint, by slug; at most 6; dimension rows stay under Dimensions.

`build_pages(services, facts, probes)`; `registry_pages(root)` loads all three and is what the CLI, CI
(`--check`) and the bot's nightly rebuild run. These sections hold no counters, so `substantive()`
keeps them whole: a template change like this one re-dates every page once, a refresh never does.

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
| `/.well-known/mcp.json` | `server.json` (the MCP registry entry: stdio, `uvx --from 'apifacts[mcp]' apifacts mcp`) plus the HTTP API under `_meta` |
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

### Structured data and machine discovery (decision 31.10)

A fact page's `<head>` carries one `<script type="application/ld+json">` (data, not code: the
"no scripts" rule above is about executable script): a schema.org `TechArticle` with `headline` = the
H1 text, `description` = the claim, `about` = the service as a `WebAPI`, `datePublished` = the fact's
`provenance.created`, `dateModified` = the page's sitemap `lastmod`, `url`, `license` = CC BY 4.0,
`keywords` = the error code. Built from the facts index (`templates.json_ld`), never from the
markdown; `<`, `>` and `&` are written as `\u003c` … so no registry text can close the element.
Retracted facts, error stubs, indexes and the home page carry none.

`/.well-known/mcp.json` republishes the repository's `server.json` and adds, under the registry's
publisher-provided `_meta` key, the stdio command and the HTTP API (`POST /v0/check`, OpenAPI,
llms.txt, no auth). MCP server cards (SEP-1649, then SEP-2127, still drafts in 10.2026, path not
settled) describe *remote* MCP endpoints; apifacts has none, so it claims no `remotes`. No A2A agent
card either: `/.well-known/agent.json` would advertise an A2A endpoint that does not exist.
`/openapi.json` gives `POST /v0/check` a summary and an agent-facing description; llms.txt links the
MCP manifest.
