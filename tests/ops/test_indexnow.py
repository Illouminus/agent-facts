"""ops/indexnow.py: submit the sitemap URLs whose lastmod moved, once, to IndexNow.

A local `httpserver` serves the sitemap; the IndexNow endpoint is a fake `post` (or a second path
on the same server): nothing leaves the machine.
"""

import json
from datetime import UTC, datetime

import httpx
import indexnow
import pytest

from apifacts.api.site import INDEXNOW_KEY

NOW = lambda: datetime(2026, 11, 1, 3, 30, tzinfo=UTC)  # noqa: E731


def sitemap(dates: dict[str, str]) -> str:
    rows = "".join(
        f"<url><loc>https://apifacts.dev{p}</loc><lastmod>{d}</lastmod></url>"
        for p, d in dates.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'
    )


class FakeIndexNow:
    def __init__(self, status: int = 200):
        self.status, self.calls = status, []

    def __call__(self, endpoint: str, body: dict) -> httpx.Response:
        self.calls.append((endpoint, body))
        return httpx.Response(self.status, text="" if self.status < 300 else "Forbidden key")


@pytest.fixture
def run(httpserver, tmp_path):
    state = tmp_path / "var" / "indexnow.json"

    def go(dates: dict[str, str], fake: FakeIndexNow, *extra: str) -> int:
        httpserver.clear()
        httpserver.expect_request("/sitemap.xml").respond_with_data(
            sitemap(dates), content_type="application/xml"
        )
        argv = ["--sitemap", httpserver.url_for("/sitemap.xml"), "--state", str(state), *extra]
        return indexnow.main(argv, post=fake, now=NOW)

    go.state = state
    return go


def test_first_run_submits_every_page_in_one_batch(run):
    fake = FakeIndexNow()
    assert run({"/": "2026-10-31", "/stripe/x": "2026-10-31"}, fake) == 0
    ((endpoint, body),) = fake.calls
    assert endpoint == "https://api.indexnow.org/indexnow"
    assert body == {
        "host": "apifacts.dev",
        "key": INDEXNOW_KEY,
        "keyLocation": f"https://apifacts.dev/{INDEXNOW_KEY}.txt",
        "urlList": ["https://apifacts.dev/", "https://apifacts.dev/stripe/x"],
    }
    state = json.loads(run.state.read_text(encoding="utf-8"))
    assert state["submitted"] == {
        "https://apifacts.dev/": "2026-10-31",
        "https://apifacts.dev/stripe/x": "2026-10-31",
    }
    assert state["last_run"]["ok"] is True and state["last_run"]["at"] == "2026-11-01T03:30:00Z"


def test_only_moved_new_and_removed_urls_go_next_time(run):
    run(
        {"/": "2026-10-31", "/stripe/x": "2026-10-31", "/stripe/gone": "2026-10-31"}, FakeIndexNow()
    )
    fake = FakeIndexNow(202)
    assert (
        run({"/": "2026-10-31", "/stripe/x": "2026-11-01", "/stripe/new": "2026-11-01"}, fake) == 0
    )
    assert fake.calls[0][1]["urlList"] == [
        "https://apifacts.dev/stripe/new",
        "https://apifacts.dev/stripe/x",
        "https://apifacts.dev/stripe/gone",
    ]
    submitted = json.loads(run.state.read_text(encoding="utf-8"))["submitted"]
    assert "https://apifacts.dev/stripe/gone" not in submitted


def test_nothing_changed_posts_nothing(run):
    dates = {"/": "2026-10-31"}
    run(dates, FakeIndexNow())
    fake = FakeIndexNow()
    assert run(dates, fake) == 0
    assert fake.calls == []
    assert json.loads(run.state.read_text(encoding="utf-8"))["last_run"]["urls"] == 0


def test_refused_submission_keeps_the_state_for_a_full_retry(run):
    assert run({"/": "2026-10-31"}, FakeIndexNow(403)) == 1
    state = json.loads(run.state.read_text(encoding="utf-8"))
    assert state["submitted"] == {}
    assert state["last_run"]["batches"] == [{"urls": 1, "status": 403, "body": "Forbidden key"}]
    fake = FakeIndexNow()
    assert run({"/": "2026-10-31"}, fake) == 0
    assert fake.calls[0][1]["urlList"] == ["https://apifacts.dev/"]


def test_dry_run_prints_and_writes_nothing(run, capsys):
    fake = FakeIndexNow()
    assert run({"/": "2026-10-31"}, fake, "--dry-run") == 0
    assert fake.calls == [] and not run.state.exists()
    out = capsys.readouterr().out
    assert "would submit 1 of 1 URLs" in out and "https://apifacts.dev/\n" in out


def test_unreachable_sitemap_fails_without_touching_the_state(tmp_path):
    state = tmp_path / "indexnow.json"
    argv = ["--sitemap", "http://127.0.0.1:9/sitemap.xml", "--state", str(state)]
    assert indexnow.main(argv, post=FakeIndexNow(), now=NOW) == 1
    assert not state.exists()


def test_foreign_urls_are_never_submitted():
    current = {"https://apifacts.dev/a": "d", "https://evil.example/b": "d"}
    assert indexnow.to_submit(current, {}) == ["https://apifacts.dev/a"]


def test_batches_of_ten_thousand(monkeypatch):
    fake = FakeIndexNow()
    monkeypatch.setattr(indexnow, "BATCH", 2)
    ok, log = indexnow.submit([f"https://apifacts.dev/{i}" for i in range(5)], "e", fake)
    assert ok and [b["urls"] for b in log] == [2, 2, 1]
