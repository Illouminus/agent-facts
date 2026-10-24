"""Auth kinds beyond a header or a query parameter, end to end in a tick (no real network):
`path_prefix` (the key inside the path, Telegram) and `google_service_account` (a minted token)."""

import json

from probe_builders import Repo
from werkzeug import Response

from agentfacts.probe.runner import TickOptions, run_tick

TELEGRAM_KEY = "123456789:AAFakeFakeFakeFakeFakeFakeFakeFake_x"
PATH_AUTH = {"kind": "path_prefix", "key_name": "acme-test", "env": "sandbox",
             "path_prefix": "/bot{key}"}


def tick(repo: Repo, httpserver, **extra):
    return run_tick(
        repo.root,
        repo.state,
        TickOptions(run_all=True, vantage="test"),
        keys_dir=repo.keys,
        base_urls={"acme": httpserver.url_for("")},
        sleep=lambda _s: None,
        environ={},
        **extra,
    )


def outputs(repo: Repo) -> bytes:
    files = [*repo.state.rglob("*"), *(repo.root / "facts").rglob("*")]
    return b"\n".join(p.read_bytes() for p in files if p.is_file())


def test_path_prefix_tick_sends_the_key_in_the_path_and_records_the_template(repo, httpserver):
    repo.service(auth=PATH_AUTH)
    repo.key(value=TELEGRAM_KEY)
    repo.probe()
    repo.fact()

    def echo(_request):
        body = {"ok": True, "description": f"token {TELEGRAM_KEY}"}
        return Response(json.dumps(body), 200, {"X-Echo": TELEGRAM_KEY},
                        content_type="application/json")

    httpserver.expect_request(f"/bot{TELEGRAM_KEY}/v1/items").respond_with_handler(echo)
    report = tick(repo, httpserver)
    assert [line.outcome for line in report.lines] == ["pass"]
    step = repo.results()[0]["steps"][0]
    assert step["path"] == "/v1/items" and step["template"] == "/v1/items"
    assert TELEGRAM_KEY.encode() not in outputs(repo)
    assert TELEGRAM_KEY.split(":")[1].encode() not in outputs(repo)
    assert TELEGRAM_KEY not in " ".join(line.detail for line in report.lines)


def test_path_prefix_with_an_unsafe_key_sends_nothing(repo, httpserver):
    repo.service(auth=PATH_AUTH)
    repo.key(value="123:abc/../../admin")
    repo.probe()
    repo.fact()
    report = tick(repo, httpserver)
    assert [(line.outcome, line.detail) for line in report.lines] == [
        ("error", "refused:key_not_path_safe: the acme key is not one plain path segment")
    ]
    assert httpserver.log == []
    assert b"admin" not in outputs(repo)
