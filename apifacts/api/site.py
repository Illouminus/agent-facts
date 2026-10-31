"""The front door (spec 06, "HTML on the domain"): `/` from README.md, the generated `pages/` as
HTML at the same paths, `/llms.txt`, `/robots.txt`, `/sitemap.xml` and the IndexNow key file. No
scripts, fonts, forms or analytics.

Rendered once, at startup, like the facts index: a new registry needs a restart. Markdown goes
through markdown-it-py with raw HTML off, so every string from a page (error strings included)
reaches the browser escaped. Links are rewritten to the domain: `pages/<service>/<slug>.md` →
`/<service>/<slug>`, `pages/<service>/index.md` → `/<service>/`, `pages/index.md` → `/registry`;
any other file of the repo → its blob on GitHub.

`<title>` and `<meta name="description">` of fact and service pages come from the facts index, not
from the rendered markdown: `Stripe API 400 amount_too_small: <error string>` is what a result list
should show, and the H1 alone carries neither the service nor the status.

Sitemap `lastmod` = the day this process first served the page's current *substance*: the
markdown with the evidence counters stripped (`templates.substantive`), hashed and remembered in
`var/sitemap-lastmod.json`. The facts are re-confirmed every night and their pages say so
(`last confirmed`, `N confirmations`), so the file's mtime, the commit date or the registry
version would move every page every day and teach crawlers that lastmod means nothing. The
fact's own dates (`created`, `history`) would miss a hand-edited claim or fix, a new sibling row
and a template change (the H1 switching to the raw error string). A page seen for the first time
gets today; a lost or unwritable state file only makes every page "changed today" once.
"""

import hashlib
import html
import json
import logging
import posixpath
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from markdown_it import MarkdownIt
from markdown_it.token import Token

from apifacts.api.facts_index import FactsIndex
from apifacts.pages import templates

log = logging.getLogger("apifacts.api")

REPO_URL = "https://github.com/Illouminus/apifacts"
BLOB = f"{REPO_URL}/blob/main"
SITE = "https://apifacts.dev"
README = "README.md"
PAGES_DIR = "pages"

CSS = (
    "body{margin:0;font:16px/1.55 system-ui,-apple-system,'Segoe UI',sans-serif;color:#1b1b1b;"
    "background:#fff}main{max-width:52rem;margin:0 auto;padding:1.5rem 1rem 3rem}"
    "nav{font-size:.9rem;margin-bottom:1rem}nav a{margin-right:1rem}a{color:#0b57d0}"
    "h1{font-size:1.5rem;line-height:1.3;overflow-wrap:anywhere}h2{font-size:1.15rem;margin-top:2rem}"
    "code{font:.9em ui-monospace,SFMono-Regular,Menlo,monospace;background:#f3f3f3;padding:0 .2em;"
    "overflow-wrap:anywhere}pre{background:#f3f3f3;padding:.75rem;overflow-x:auto}"
    "pre code{padding:0;background:none}blockquote{margin:1rem 0;padding:0 1rem;"
    "border-left:3px solid #ccc;color:#444}table{border-collapse:collapse;display:block;"
    "overflow-x:auto}th,td{border:1px solid #ddd;padding:.3rem .6rem}hr{border:0;"
    "border-top:1px solid #ddd;margin:2rem 0}"
    "@media(prefers-color-scheme:dark){body{background:#111;color:#e6e6e6}a{color:#8ab4f8}"
    "code,pre{background:#222}blockquote{color:#bbb;border-color:#555}th,td{border-color:#333}}"
)
NAV = (
    '<nav><a href="/">apifacts</a><a href="/registry">Registry</a><a href="/docs">API</a>'
    f'<a href="{REPO_URL}">GitHub</a></nav>'
)

SITEMAP_URL = f"{SITE}/sitemap.xml"
ROBOTS = f"User-agent: *\nAllow: /\n\nSitemap: {SITEMAP_URL}\n"
# IndexNow (indexnow.org): the key only proves that whoever submits URLs for apifacts.dev controls
# what apifacts.dev serves, so it is public by design (served at /<key>.txt). A constant, not a
# host file: the route and ops/indexnow.py can never disagree, and nothing extra to deploy.
# Rotate = new value here + deploy; the engines re-fetch keyLocation on the next submission.
INDEXNOW_KEY = "2512f7f2a72f05dc4e4a02300eaac754"
LASTMOD_STATE = "var/sitemap-lastmod.json"


@dataclass(frozen=True)
class Page:
    body: bytes
    etag: str


@dataclass(frozen=True)
class Head:
    title: str | None  # None: the page's H1, clipped
    description: str | None = None


HOME_DESCRIPTION = (
    "Verified facts about what APIs actually return, for AI agents. "
    "pip install apifacts-pytest · POST https://apifacts.dev/v0/check"
)


def _page(title: str, content: str, description: str | None = None) -> Page:
    meta = f'<meta name="description" content="{html.escape(description)}">' if description else ""
    doc = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title>{meta}"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>{CSS}</style></head>"
        f"<body><main>{NAV}{content}</main></body></html>"
    )
    return text_page(doc)


def text_page(text: str) -> Page:
    body = text.encode("utf-8")
    return Page(body, f'"{hashlib.sha256(body).hexdigest()[:32]}"')


def url_for(repo_path: str) -> str | None:
    """Domain path of a page file (`pages/...md`), None for anything else."""
    if not repo_path.startswith(f"{PAGES_DIR}/") or not repo_path.endswith(".md"):
        return None
    parts = repo_path[len(PAGES_DIR) + 1 : -3].split("/")
    if parts == ["index"]:
        return "/registry"
    if len(parts) == 2:
        return f"/{parts[0]}/" if parts[1] == "index" else f"/{parts[0]}/{parts[1]}"
    return None


def _rewrite(href: str, source: str) -> str:
    """A relative link of the markdown file `source` (repo path) → its address on the domain."""
    if not href or href.startswith(("#", "/")) or "://" in href or href.startswith("mailto:"):
        return href
    path, sep, fragment = href.partition("#")
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    if target.startswith("../") or target == "..":
        return href
    if path.endswith("/"):
        target += "/"
    page = url_for(target)
    if page is None:
        kind = "tree" if path.endswith("/") else "blob"
        page = f"{REPO_URL}/{kind}/main/{target.rstrip('/')}"
    return page + sep + fragment


def _title(tokens: list[Token]) -> str:
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h1" and i + 1 < len(tokens):
            inline = tokens[i + 1]
            return "".join(c.content for c in inline.children or () if c.content) or "apifacts"
    return "apifacts"


def render(
    markdown: str, source: str, description: str | None = None, title: str | None = None
) -> Page:
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = md.parse(markdown)
    for token in tokens:
        for child in token.children or ():
            if child.type == "link_open":
                child.attrSet("href", _rewrite(str(child.attrGet("href") or ""), source))
    body = md.renderer.render(tokens, md.options, {})
    if title is None:
        h1 = _title(tokens)
        limit = templates.HEAD_TITLE_MAX - len(templates.HEAD_SUFFIX)
        title = h1 if h1 == "apifacts" else templates.clip_words(h1, limit) + templates.HEAD_SUFFIX
    return _page(title, body, description)


NOT_FOUND = _page(
    "Not found · apifacts",
    "<h1>Not found</h1><p>No such page. "
    'The registry lists every service: <a href="/registry">/registry</a>.</p>',
)


def llms_txt(services: list[tuple[str, str, int]], version: str, opt_out: str) -> str:
    lines = [
        "# apifacts",
        "",
        "> Open registry of verified, dated facts about what third-party machine interfaces"
        " (HTTP APIs, SDKs, CLIs) actually do today. Facts come from deterministic probes;"
        " no language model is in the verification path.",
        "",
        f"Registry version {version}. Code MIT, data CC BY 4.0. Source: {REPO_URL}",
        "",
        "## API",
        "",
        f"- [POST /v0/check]({SITE}/v0/check): send the failing request as"
        ' `{"target":{"method":"GET","url":"https://api.stripe.com/v1/customers"},'
        '"error":{"status":401,"body_excerpt":"..."}}`; get the matching facts with typed fixes.'
        " A target on a registered template is stored as one normalized observation"
        " (no bodies, headers, query strings or raw IPs).",
        f"- [GET /v0/services]({SITE}/v0/services): services, hosts and fact counts",
        f"- [GET /v0/facts/{{service}}]({SITE}/v0/facts/stripe): every fact of a service (JSON)",
        f"- [GET /v0/facts/{{service}}/{{slug}}]({SITE}/v0/facts/stripe/missing-api-key-401):"
        " one fact",
        f"- [OpenAPI schema]({SITE}/openapi.json) · [Swagger UI]({SITE}/docs)",
        f"- [Fact schema]({BLOB}/schema/fact.schema.json)",
        "",
        "## Services",
        "",
        *(f"- [{name}]({SITE}/{key}/): {count} facts" for key, name, count in services),
        "",
        "## Optional",
        "",
        f"- [Registry index]({SITE}/registry)",
        f"- [Sitemap]({SITEMAP_URL}): every page, lastmod = its last change of substance",
        "- Install: `pip install apifacts-pytest` (pytest plugin) ·"
        " `uvx apifacts check <url>` (CLI)",
        f"- Probe opt-out and contact: {opt_out}",
        "",
    ]
    return "\n".join(lines)


# An error stub keeps its H1 (the normalized string) as the title; only the description is shared.
ERROR_STUB_HEAD = Head(
    None,
    "An error string as apifacts normalizes it (lowercase, digits as #): the match signature of "
    "POST /v0/check, and every API fact that returns it.",
)


def heads(index: FactsIndex) -> dict[str, Head]:
    """Domain path → `<title>`/description for the registry, service and fact pages the index
    knows (a fact skipped by the index keeps its H1 as the title)."""
    out = {
        "/registry": Head(
            "apifacts registry: services and fact counts",
            "Every service in the apifacts registry with its facts by status: verified by a "
            "probe, official, reported, stale, retracted.",
        )
    }
    for entry in index.services.values():
        live = [f.fact for f in entry.facts]
        out[f"/{entry.key}/"] = Head(*templates.service_head(entry.service, live))
    for indexed in index.all_facts():
        fact = indexed.fact
        if (entry := index.services.get(fact.service)) is not None:
            path = f"/{fact.service}/{templates.slug_of(fact)}"
            title = templates.head_title(fact, entry.service)
            out[path] = Head(title, templates.head_description(fact))
    return out


@dataclass(frozen=True)
class Site:
    pages: dict[str, Page]
    sitemap: Page


def load_site(root: Path, index: FactsIndex, today: str, state: Path | None) -> Site:
    """Every page of the domain (README.md and each page file) plus the sitemap. `state` keeps
    each page's lastmod across restarts; None = nothing remembered (every page dated `today`)."""
    sources: dict[str, tuple[str, str]] = {}  # domain path → (repo path, markdown)
    if (root / README).is_file():
        sources["/"] = (README, (root / README).read_text(encoding="utf-8"))
    pages_dir = root / PAGES_DIR
    if pages_dir.is_dir():
        for file in sorted(pages_dir.rglob("*.md")):
            source = file.relative_to(root).as_posix()
            if (path := url_for(source)) is not None:
                sources[path] = (source, file.read_text(encoding="utf-8"))
    known = heads(index) | {"/": Head("apifacts", HOME_DESCRIPTION)}
    pages = {}
    for path, (source, text) in sources.items():
        head = known.get(path) or (ERROR_STUB_HEAD if path.startswith("/errors/") else None)
        pages[path] = render(text, source, *((head.description, head.title) if head else ()))
    digests = {
        path: hashlib.sha256(templates.substantive(text).encode("utf-8")).hexdigest()
        for path, (_, text) in sources.items()
    }
    return Site(pages, text_page(sitemap_xml(lastmods(digests, state, today))))


_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def lastmods(digests: Mapping[str, str], state: Path | None, today: str) -> dict[str, str]:
    """Domain path → `YYYY-MM-DD`: the remembered date while the digest is unchanged, else today.
    Pages gone from the site are forgotten; the file is rewritten only when something changed."""
    old: dict = {}
    if state is not None:
        try:
            loaded = json.loads(state.read_text(encoding="utf-8")).get("pages")
            old = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError, AttributeError):
            pass
    new: dict[str, dict[str, str]] = {}
    for path, digest in digests.items():
        seen = old.get(path)
        same = isinstance(seen, dict) and seen.get("sha256") == digest
        date = seen["lastmod"] if same and _DAY.match(str(seen.get("lastmod"))) else today
        new[path] = {"sha256": digest, "lastmod": date}
    if state is not None and new != old:
        try:
            state.parent.mkdir(parents=True, exist_ok=True)
            tmp = state.with_name(state.name + ".tmp")
            tmp.write_text(json.dumps({"pages": new}, indent=1, sort_keys=True), encoding="utf-8")
            tmp.replace(state)
        except OSError as exc:
            log.warning("sitemap lastmod state not saved (%s): %s", state, exc)
    return {path: entry["lastmod"] for path, entry in new.items()}


def _sitemap_order(path: str) -> tuple[int, str]:
    return (0 if path == "/" else 1 if path == "/registry" else 2, path)


def sitemap_xml(dates: Mapping[str, str]) -> str:
    rows = "".join(
        f"<url><loc>{escape(SITE + path)}</loc><lastmod>{dates[path]}</lastmod></url>\n"
        for path in sorted(dates, key=_sitemap_order)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{rows}</urlset>\n"
    )
