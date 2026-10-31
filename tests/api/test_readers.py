"""Reader counts (apifacts/api/readers.py): User-Agent family × path class × status class per UTC
day, merged into `<dir>/<day>.json`; never the raw User-Agent, the path, the query or the IP."""

import asyncio
import json
import time
from collections import Counter
from datetime import UTC, datetime

import pytest
from api_fixtures import PEER, STRIPE_PI
from typer.testing import CliRunner

from apifacts.api import readers
from apifacts.api.readers import ReaderCounts, family_of, merge_day, path_class, read_readers
from apifacts.cli import app as cli

DAY = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
CHROME = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


@pytest.mark.parametrize(
    ("ua", "family"),
    [
        (
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; "
            "+https://openai.com/bot",
            "ChatGPT-User",
        ),
        (
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; "
            "+https://openai.com/gptbot",
            "GPTBot",
        ),
        (
            "Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",
            "OAI-SearchBot",
        ),
        (
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; "
            "+claudebot@anthropic.com)",
            "ClaudeBot",
        ),
        ("Mozilla/5.0 (compatible; Claude-User/1.0; +Claude-User@anthropic.com)", "Claude-User"),
        ("Mozilla/5.0 (compatible; Claude-SearchBot/1.0)", "Claude-SearchBot"),
        ("anthropic-ai", "anthropic-ai"),
        (
            "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
            "PerplexityBot",
        ),
        (
            "Mozilla/5.0 (compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
            "Perplexity-User",
        ),
        (
            "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; "
            "+http://www.google.com/bot.html)",
            "Googlebot",
        ),
        ("Mozilla/5.0 (compatible; GoogleOther)", "Google-other"),
        ("Google-CloudVertexBot", "Google-other"),
        ("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", "Bingbot"),
        (
            "Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
            "Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)",
            "Applebot",
        ),
        (
            "Mozilla/5.0 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)",
            "Amazonbot",
        ),
        (
            "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile "
            "Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)",
            "Bytespider",
        ),
        ("CCBot/2.0 (https://commoncrawl.org/faq/)", "CCBot"),
        (
            "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)",
            "meta-externalagent",
        ),
        ("DuckAssistBot/1.2; (+http://duckduckgo.com/duckassistbot.html)", "DuckAssistBot"),
        ("Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)", "YandexBot"),
        ("Mozilla/5.0 (compatible; ExaBot/1.0)", "ExaBot"),
        ("Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)", "other-bot"),
        ("apifacts-cli/0.2.1 (+https://github.com/Illouminus/apifacts)", "apifacts-cli"),
        ("apifacts-pytest/0.2.1 (+https://github.com/Illouminus/apifacts)", "apifacts-pytest"),
        ("apifacts-mcp/0.2.1 (+https://github.com/Illouminus/apifacts)", "apifacts-mcp"),
        ("curl/8.7.1", "script"),
        ("python-requests/2.32.3", "script"),
        ("python-httpx/0.28.1", "script"),
        ("Python/3.12 aiohttp/3.10.0", "script"),
        ("node-fetch/1.0 (+https://github.com/bitinn/node-fetch)", "script"),
        ("undici", "script"),
        ("Go-http-client/2.0", "script"),
        (CHROME, "browser"),
        ("", "unknown"),
        (None, "unknown"),
        ("SomethingNobodyKnows/1.0", "other"),
    ],
)
def test_user_agent_families(ua, family):
    assert family_of(ua) == family


def test_every_family_has_a_known_group_and_a_unique_name():
    names = [family for family, _, _ in readers.FAMILIES]
    assert len(names) == len(set(names))
    assert {group for _, group, _ in readers.FAMILIES} <= set(readers.GROUPS)
    assert readers.group_of("RenamedLongAgo") == readers.OTHER


@pytest.mark.parametrize(
    ("path", "cls"),
    [
        ("/", "home"),
        ("/registry", "registry"),
        ("/stripe", "service_index"),
        ("/stripe/", "service_index"),
        ("/stripe/missing-api-key-401", "fact_page"),
        ("/llms.txt", "llms"),
        ("/robots.txt", "robots"),
        ("/sitemap.xml", "sitemap"),
        ("/v0/check", "api_check"),
        ("/v0/facts/stripe", "api_read"),
        ("/v0/services", "api_read"),
        ("/healthz", "api_read"),
        ("/docs", "docs"),
        ("/openapi.json", "docs"),
        ("/favicon.ico", "other"),
        ("/wp-login.php", "other"),
        ("/.env", "other"),
        ("/.well-known/security.txt", "other"),
        ("/a/b/c", "other"),
    ],
)
def test_path_classes(path, cls):
    assert path_class(path) == cls


def test_counts_land_in_the_day_file_at_shutdown_without_raw_values(make_client, tmp_path):
    out = tmp_path / "readers"
    client = make_client(("8.8.8.8", 1), utcnow=lambda: DAY, readers_dir=out)
    secret_ua = "ClaudeBot/1.0 marker-7f3a"
    client.get("/llms.txt", headers={"User-Agent": secret_ua})
    client.get("/robots.txt?token=marker-q", headers={"User-Agent": secret_ua})
    client.get("/nope/nothing-here", headers={"User-Agent": CHROME})
    client.post(
        "/v0/check",
        json={"target": {"method": "POST", "url": STRIPE_PI}},
        headers={"User-Agent": "apifacts-pytest/0.2.1"},
    )
    client.get("/v0/services", headers={"User-Agent": ""})
    client.__exit__(None, None, None)  # lifespan shutdown: the flush
    text = (out / "2026-10-30.json").read_text()
    for raw in ("marker", "8.8.8.8", "nothing-here", "token", "Mozilla"):
        assert raw not in text
    doc = json.loads(text)
    assert doc["day"] == "2026-10-30"
    assert doc["counts"] == {
        "ClaudeBot": {"llms": {"2xx": 1}, "robots": {"2xx": 1}},
        "browser": {"fact_page": {"4xx": 1}},
        "apifacts-pytest": {"api_check": {"2xx": 1}},
        "unknown": {"api_read": {"2xx": 1}},
    }


def test_rate_limited_calls_are_counted_too(make_client, tmp_path):
    out = tmp_path / "readers"
    client = make_client(utcnow=lambda: DAY, readers_dir=out, per_net=1)
    body, ua = {"target": {"method": "POST", "url": STRIPE_PI}}, {"User-Agent": "curl/8.7.1"}
    assert client.post("/v0/check", json=body, headers=ua).status_code == 200
    assert client.post("/v0/check", json=body, headers=ua).status_code == 429
    pending = client.app.state.readers.pending()
    assert pending == {
        "2026-10-30": {("script", "api_check", "2xx"): 1, ("script", "api_check", "4xx"): 1}
    }


def test_default_directory_is_next_to_the_db(make_client, db_path, monkeypatch):
    monkeypatch.delenv("APIFACTS_READERS_DIR", raising=False)
    client = make_client(PEER, utcnow=lambda: DAY)
    client.get("/robots.txt", headers={"User-Agent": "GPTBot/1.2"})
    client.__exit__(None, None, None)
    assert (db_path.parent / "readers" / "2026-10-30.json").is_file()


def test_merge_adds_to_the_existing_file(tmp_path):
    merge_day(tmp_path, "2026-10-30", Counter({("GPTBot", "home", "2xx"): 2}))
    merge_day(
        tmp_path,
        "2026-10-30",
        Counter({("GPTBot", "home", "2xx"): 3, ("CCBot", "fact_page", "4xx"): 1}),
    )
    got = read_readers(tmp_path, ["2026-10-29", "2026-10-30"])
    assert got.counts == Counter({("GPTBot", "home", "2xx"): 5, ("CCBot", "fact_page", "4xx"): 1})
    assert (got.days_found, got.total) == (1, 6)
    assert not list(tmp_path.glob("*.tmp"))


def test_a_broken_file_is_set_aside_not_lost(tmp_path):
    (tmp_path / "2026-10-30.json").write_text("{not json")
    merge_day(tmp_path, "2026-10-30", Counter({("GPTBot", "home", "2xx"): 1}))
    assert (tmp_path / "2026-10-30.json.bad").read_text() == "{not json"
    assert read_readers(tmp_path, ["2026-10-30"]).total == 1


def test_a_failed_write_keeps_the_counts_for_the_next_flush(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    counts = ReaderCounts(blocker / "readers")  # a directory under a file: mkdir fails
    counts.add("2026-10-30", ("GPTBot", "home", "2xx"))
    assert counts.flush() == 0
    assert counts.pending() == {"2026-10-30": {("GPTBot", "home", "2xx"): 1}}
    counts.directory = tmp_path / "readers"
    assert counts.flush() == 1
    assert counts.pending() == {}


def test_reading_skips_unreadable_days_and_reports_a_missing_directory(tmp_path):
    (tmp_path / "2026-10-29.json").write_text('{"counts": {"GPTBot": {"home": {"2xx": "x"}}}}')
    merge_day(tmp_path, "2026-10-30", Counter({("GPTBot", "home", "2xx"): 1}))
    got = read_readers(tmp_path, ["2026-10-29", "2026-10-30"])
    assert (got.total, got.bad_files) == (1, 1)
    assert not read_readers(tmp_path / "none", ["2026-10-30"]).available


def test_stats_readers_prints_a_table(tmp_path):
    merge_day(
        tmp_path,
        "2026-10-30",
        Counter(
            {
                ("ChatGPT-User", "fact_page", "2xx"): 3,
                ("ChatGPT-User", "home", "2xx"): 1,
                ("GPTBot", "fact_page", "4xx"): 2,
                ("browser", "home", "2xx"): 5,
            }
        ),
    )
    merge_day(tmp_path, "2026-10-20", Counter({("GPTBot", "home", "2xx"): 100}))  # out of range
    result = CliRunner().invoke(
        cli,
        [
            "stats",
            "readers",
            "--dir",
            str(tmp_path),
            "--days",
            "7",
            "--now",
            "2026-10-31T09:00:00+00:00",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0] == (
        "readers 2026-10-25..2026-10-31 UTC (1/7 days with data, today partial): 11 requests"
    )
    assert lines[2].split() == [
        "ai_agent",
        "ChatGPT-User",
        "4",
        "4",
        "0",
        "0",
        "0",
        "fact_page",
        "3,",
        "home",
        "1",
    ]
    assert lines[3].split()[:3] == ["ai_crawler", "GPTBot", "2"]
    assert lines[4].split()[:3] == ["browser", "browser", "5"]


def test_stats_readers_without_a_directory_exits_1(tmp_path):
    result = CliRunner().invoke(cli, ["stats", "readers", "--dir", str(tmp_path / "none")])
    assert result.exit_code == 1


def test_periodic_flush_writes_while_the_api_runs(make_client, tmp_path):
    out = tmp_path / "readers"
    client = make_client(utcnow=lambda: DAY, readers_dir=out, readers_flush_s=0.01)
    client.get("/robots.txt", headers={"User-Agent": "CCBot/2.0"})
    deadline = time.monotonic() + 5
    while not (out / "2026-10-30.json").is_file() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert read_readers(out, ["2026-10-30"]).counts == Counter({("CCBot", "robots", "2xx"): 1})


def test_an_exception_in_the_app_counts_as_5xx():
    async def broken(scope, receive, send):
        raise RuntimeError("boom")

    counts = ReaderCounts()
    middleware = readers.ReadersMiddleware(broken, counts, lambda: DAY)
    scope = {"type": "http", "path": "/stripe/x", "headers": [(b"user-agent", b"GPTBot/1.2")]}
    with pytest.raises(RuntimeError):
        asyncio.run(middleware(scope, None, None))
    assert counts.pending() == {"2026-10-30": {("GPTBot", "fact_page", "5xx"): 1}}
