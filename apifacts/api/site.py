"""The front door (spec 06, "HTML on the domain"): `/` from README.en.md, the generated `pages/` as
HTML at the same paths, `/llms.txt` and `/robots.txt`. No scripts, fonts, forms or analytics.

Rendered once, at startup, like the facts index: a new registry needs a restart. Markdown goes
through markdown-it-py with raw HTML off, so every string from a page (error strings included)
reaches the browser escaped. Links are rewritten to the domain: `pages/<service>/<slug>.md` →
`/<service>/<slug>`, `pages/<service>/index.md` → `/<service>/`, `pages/index.md` → `/registry`;
any other file of the repo → its blob on GitHub.
"""

import hashlib
import html
import posixpath
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

REPO_URL = "https://github.com/Illouminus/apifacts"
BLOB = f"{REPO_URL}/blob/main"
SITE = "https://apifacts.dev"
README = "README.en.md"
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

ROBOTS = "User-agent: *\nAllow: /\n"


@dataclass(frozen=True)
class Page:
    body: bytes
    etag: str


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


def render(markdown: str, source: str, description: str | None = None) -> Page:
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = md.parse(markdown)
    for token in tokens:
        for child in token.children or ():
            if child.type == "link_open":
                child.attrSet("href", _rewrite(str(child.attrGet("href") or ""), source))
    title = _title(tokens)
    body = md.renderer.render(tokens, md.options, {})
    return _page(title if title == "apifacts" else f"{title} · apifacts", body, description)


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
        "- Install: `pip install apifacts-pytest` (pytest plugin) ·"
        " `uvx apifacts check <url>` (CLI)",
        f"- Probe opt-out and contact: {opt_out}",
        "",
    ]
    return "\n".join(lines)


def load_pages(root: Path) -> dict[str, Page]:
    """Domain path → rendered page, for README.en.md and every page file."""
    pages: dict[str, Page] = {}
    readme = root / README
    if readme.is_file():
        pages["/"] = render(readme.read_text(encoding="utf-8"), README, HOME_DESCRIPTION)
    pages_dir = root / PAGES_DIR
    if pages_dir.is_dir():
        for file in sorted(pages_dir.rglob("*.md")):
            source = file.relative_to(root).as_posix()
            if (path := url_for(source)) is not None:
                pages[path] = render(file.read_text(encoding="utf-8"), source)
    return pages
