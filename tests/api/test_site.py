"""The front door (spec 06, "HTML on the domain"): README and pages as HTML, llms.txt, robots."""

import pytest

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


@pytest.fixture
def site(repo, make_client):
    files = {
        "README.en.md": README,
        "pages/index.md": INDEX,
        "pages/stripe/index.md": SERVICE,
        "pages/stripe/missing-api-key-401.md": FACT,
        "pages/errors/0604a899fa8d.md": "# `you did not provide an api key`\n",
    }
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return make_client()


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
                   "https://apifacts.dev/stripe/"):
        assert needle in r.text


def test_robots_txt(site):
    r = site.get("/robots.txt")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert r.text == "User-agent: *\nAllow: /\n"


def test_no_pages_no_crash(client):
    assert client.get("/").status_code == 404
    assert client.get("/llms.txt").status_code == 200
