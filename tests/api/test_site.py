"""The front door (spec 06, "HTML on the domain"): README and pages as HTML, llms.txt, robots,
the sitemap with its substance-based lastmod, the IndexNow key file."""

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import pytest

from apifacts.api.site import INDEXNOW_KEY

README = """# apifacts

```bash
pip install apifacts-pytest
```

See [the registry](pages/index.md), [deploy](ops/README.md#deploy) and [MIT](LICENSE).
"""
INDEX = (
    "# apifacts registry\n\n| Service | Facts |\n| --- | ---: |\n"
    "| [Stripe](stripe/index.md) | 1 |\n"
)
SERVICE = "# Stripe API\n\n- ✅ [`no api key`](missing-api-key-401.md) · GET /v1/customers\n"
FACT = """# `<script>alert(1)</script> you did not provide an api key`

**Stripe API · GET /v1/customers · HTTP 401**

Back to [Stripe](index.md), same error on [errors](../errors/0604a899fa8d.md).

YAML: [facts/stripe/missing-api-key-401.yaml](../../facts/stripe/missing-api-key-401.yaml)

<img src=x onerror=alert(2)>
"""


CUSTOMER = (
    "# `No such customer: 'cus_123'`\n\n"
    "**Stripe · GET /v1/customers/{id} · HTTP 404 `resource_missing`**\n\n"
    "Status: 🟡 reported · first seen 2026-10-01 · last confirmed 2026-10-02 · "
    "3 confirmations from 1 vantage\n\n"
    "> GET /v1/customers/{id} returns HTTP 404 resource_missing for a deleted customer.\n"
)
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def day(n: int):
    return lambda: datetime(2026, 11, n, 4, 30, tzinfo=UTC)


@pytest.fixture
def site(repo, make_client):
    write_pages(repo)
    return make_client()


def write_pages(repo, **override):
    files = {
        "README.md": README,
        "pages/index.md": INDEX,
        "pages/stripe/index.md": SERVICE,
        "pages/stripe/missing-api-key-401.md": FACT,
        "pages/stripe/customer-not-found.md": CUSTOMER,
        "pages/stripe/withdrawn.md": "# POST /v1/payment\\_intents was said to return HTTP 503\n",
        "pages/errors/0604a899fa8d.md": "# `you did not provide an api key`\n",
        **override,
    }
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("path", "needle"),
    [
        ("/", "pip install apifacts-pytest"),
        ("/registry", "apifacts registry"),
        ("/stripe/", "Stripe API"),
        ("/stripe/missing-api-key-401", "HTTP 401"),
        ("/errors/0604a899fa8d", "you did not provide an api key"),
    ],
)
def test_pages_are_html(site, path, needle):
    r = site.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/html; charset=utf-8"
    assert r.headers["cache-control"] == "public, max-age=300"
    assert r.text.startswith("<!doctype html>")
    assert needle in r.text
    assert "<script" not in r.text and "<img" not in r.text and "<link" not in r.text


def test_home_head_names_the_install_line(site):
    head = site.get("/").text[:300]
    assert "<title>apifacts</title>" in head
    assert "pip install apifacts-pytest" in head


def test_page_content_is_escaped(site):
    text = site.get("/stripe/missing-api-key-401").text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "<img" not in text and "&lt;img src=x onerror=alert(2)&gt;" in text


def test_links_point_at_the_domain(site):
    text = site.get("/stripe/missing-api-key-401").text
    assert 'href="/stripe/"' in text
    assert 'href="/errors/0604a899fa8d"' in text
    assert (
        'href="https://github.com/Illouminus/apifacts/blob/main/facts/stripe/'
        'missing-api-key-401.yaml"' in text
    )
    assert 'href="missing-api-key-401"' not in site.get("/stripe/").text
    assert 'href="/stripe/missing-api-key-401"' in site.get("/stripe/").text
    assert 'href="/stripe/"' in site.get("/registry").text
    home = site.get("/").text
    assert 'href="/registry"' in home
    assert 'href="https://github.com/Illouminus/apifacts/blob/main/ops/README.md#deploy"' in home
    assert 'href="https://github.com/Illouminus/apifacts/blob/main/LICENSE"' in home


def test_service_without_slash_redirects_relative(site):
    r = site.get("/stripe", follow_redirects=False)
    assert r.status_code == 308 and r.headers["location"] == "/stripe/"


@pytest.mark.parametrize("path", ["/nope/", "/nope", "/stripe/nope", "/stripe/index"])
def test_unknown_page_is_an_html_404(site, path):
    r = site.get(path, follow_redirects=False)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize("path", ["/v0", "/v0/facts", "/v0/", "/v0/nope/x"])
def test_api_paths_keep_the_json_404(site, path):
    r = site.get(path, follow_redirects=False)
    assert r.status_code == 404
    assert r.json()["error"]["code"] in {"not_found", "unknown_service", "unknown_fact"}


@pytest.mark.parametrize(
    ("method", "path", "allow"),
    [("GET", "/v0/check", "POST"), ("HEAD", "/v0/services", "GET"), ("PUT", "/v0/check", "POST")],
)
def test_api_paths_keep_the_json_405(site, method, path, allow):
    """A /v0 route asked with another method answers 405, not the page catch-all's 404."""
    r = site.request(method, path)
    assert r.status_code == 405
    assert r.headers["allow"] == allow
    if method != "HEAD":
        assert r.json()["error"]["code"] == "method_not_allowed"


def test_api_routes_still_win(site):
    assert site.get("/healthz").json()["ok"] is True
    assert site.get("/docs").status_code == 200
    paths = site.get("/openapi.json").json()["paths"]
    assert not any(p in paths for p in ("/", "/llms.txt", "/robots.txt", "/{service}/{slug}"))


def test_head_is_answered(site):
    r = site.head("/stripe/missing-api-key-401")
    assert r.status_code == 200 and r.headers["content-type"] == "text/html; charset=utf-8"
    assert site.head("/stripe/nope").status_code == 404


def test_etag_round_trip(site):
    etag = site.get("/stripe/missing-api-key-401").headers["etag"]
    r = site.get("/stripe/missing-api-key-401", headers={"If-None-Match": etag})
    assert r.status_code == 304 and r.content == b""


def test_llms_txt(site):
    r = site.get("/llms.txt")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert r.text.startswith("# apifacts\n")
    for needle in ("/v0/check", "/v0/services", "/openapi.json", "CC BY 4.0", "MIT",
                   "https://github.com/Illouminus/apifacts", "opt-out",
                   "https://apifacts.dev/stripe/", "https://apifacts.dev/sitemap.xml"):
        assert needle in r.text


def test_robots_txt(site):
    r = site.get("/robots.txt")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert r.text == "User-agent: *\nAllow: /\n\nSitemap: https://apifacts.dev/sitemap.xml\n"


# ── head: title and description from the facts index ─────────────────────────────────────────


def _head(text: str) -> str:
    return text[: text.index("</head>")]


def test_fact_page_title_leads_with_service_status_code_then_the_error_string(site):
    head = _head(site.get("/stripe/customer-not-found").text)
    assert (
        "<title>Stripe 404 resource_missing: No such customer: &#x27;cus_123&#x27; · apifacts"
        "</title>"
    ) in head
    assert (
        '<meta name="description" content="GET /v1/customers/{id} returns HTTP 404 '
        'resource_missing for a deleted customer.">'
    ) in head


def test_retracted_fact_page_says_so_in_the_head(site):
    head = _head(site.get("/stripe/withdrawn").text)
    assert "<title>Stripe 503: POST /v1/payment_intents was said to return HTTP 503 during" in head
    assert "(retracted) · apifacts</title>" in head
    assert 'content="Retracted. POST /v1/payment_intents' in head


def test_page_unknown_to_the_index_keeps_its_h1_title(site):
    head = _head(site.get("/stripe/missing-api-key-401").text)
    assert "<title>&lt;script&gt;alert(1)&lt;/script&gt; you did not provide an api key" in head
    assert 'name="description"' not in head


def test_error_stub_keeps_its_h1_title_and_gets_a_description(site):
    head = _head(site.get("/errors/0604a899fa8d").text)
    assert "<title>you did not provide an api key · apifacts</title>" in head
    assert '<meta name="description" content="An error string as apifacts normalizes it' in head


def test_service_page_head(site):
    head = _head(site.get("/stripe/").text)
    assert "<title>Stripe: errors, limits and quirks · apifacts</title>" in head
    assert '<meta name="description" content="What Stripe actually returns: 4 facts (' in head
    assert "Hosts: api.stripe.com." in head


# ── sitemap, IndexNow key ──────────────────────────────────────────────────────────────────────


def _sitemap(client) -> dict[str, str]:
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/xml; charset=utf-8"
    root = ET.fromstring(r.content)
    return {
        url.findtext(f"{SITEMAP_NS}loc"): url.findtext(f"{SITEMAP_NS}lastmod")
        for url in root.iter(f"{SITEMAP_NS}url")
    }


def test_sitemap_lists_every_html_page(repo, make_client):
    write_pages(repo)
    dates = _sitemap(make_client(utcnow=day(1)))
    assert list(dates)[:2] == ["https://apifacts.dev/", "https://apifacts.dev/registry"]
    assert set(dates) == {
        f"https://apifacts.dev{p}"
        for p in ("/", "/registry", "/stripe/", "/stripe/missing-api-key-401",
                  "/stripe/customer-not-found", "/stripe/withdrawn", "/errors/0604a899fa8d")
    }
    assert set(dates.values()) == {"2026-11-01"}
    state = json.loads((repo / "var" / "sitemap-lastmod.json").read_text(encoding="utf-8"))
    assert state["pages"]["/stripe/"]["lastmod"] == "2026-11-01"


def test_lastmod_ignores_a_refresh_and_moves_on_substance(repo, make_client):
    """The nightly refresh rewrites `last confirmed` and the counters: not a change. A new claim
    is; a page that disappears is forgotten."""
    write_pages(repo)
    _sitemap(make_client(utcnow=day(1)))
    refreshed = CUSTOMER.replace("last confirmed 2026-10-02 · 3 confirmations from 1 vantage",
                                 "last confirmed 2026-11-02 · 9 confirmations from 2 vantages")
    write_pages(repo, **{"pages/stripe/customer-not-found.md": refreshed})
    assert set(_sitemap(make_client(utcnow=day(2))).values()) == {"2026-11-01"}

    edited = refreshed.replace("for a deleted customer", "for a deleted or unknown customer")
    write_pages(repo, **{"pages/stripe/customer-not-found.md": edited})
    (repo / "pages/stripe/withdrawn.md").unlink()
    dates = _sitemap(make_client(utcnow=day(3)))
    assert dates.pop("https://apifacts.dev/stripe/customer-not-found") == "2026-11-03"
    assert "https://apifacts.dev/stripe/withdrawn" not in dates
    assert set(dates.values()) == {"2026-11-01"}


def test_unreadable_lastmod_state_dates_every_page_today(repo, make_client):
    write_pages(repo)
    (repo / "var").mkdir()
    (repo / "var" / "sitemap-lastmod.json").write_text("{not json", encoding="utf-8")
    assert set(_sitemap(make_client(utcnow=day(5))).values()) == {"2026-11-05"}


def test_indexnow_key_file(site):
    r = site.get(f"/{INDEXNOW_KEY}.txt")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert r.text == INDEXNOW_KEY
    assert site.get("/0000000000000000.txt").status_code == 404


def test_no_pages_no_crash(client):
    assert client.get("/").status_code == 404
    assert client.get("/llms.txt").status_code == 200
