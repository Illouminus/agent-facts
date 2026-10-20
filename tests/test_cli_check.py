import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentfacts.cli import app
from agentfacts.client.render import TITLE
from agentfacts.schema.yamlio import load_yaml, plain

runner = CliRunner()
VALID = Path(__file__).parent / "fixtures" / "valid"
FACT_FILE = "fact-idempotency-key-reuse-different-params.yaml"
URL = "https://api.stripe.com/v1/payment_intents?expand[]=customer"
SECRET = "sk_test_abcdefgh12345678"


def answer():
    fact = plain(load_yaml(VALID / FACT_FILE))
    return {
        "service": "stripe",
        "matched_template": {"method": "POST", "path": "/v1/payment_intents"},
        "facts": [fact],
        "registry": {"version": "2026-10-20", "license": "CC-BY-4.0"},
    }


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    for name in ("AGENTFACTS_DISABLE", "AGENTFACTS_SNAPSHOT", "AGENTFACTS_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture
def server(httpserver, env):
    env.setenv("AGENTFACTS_ENDPOINT", httpserver.url_for("").rstrip("/"))
    return httpserver


def posted(httpserver):
    (request,) = [r for r, _ in httpserver.log if r.path == "/v0/check"]
    return request


def test_check_prints_the_section(server, tmp_path):
    server.expect_request("/v0/check", method="POST").respond_with_json(answer())
    body = tmp_path / "body.json"
    body.write_text(f'{{"error": {{"code": "idempotency_error", "message": "key {SECRET}"}}}}')
    result = runner.invoke(
        app, ["check", URL, "-X", "post", "--status", "400", "--body", str(body)]
    )
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert f" {TITLE} " in lines[0] and lines[0].startswith("─")
    assert lines[1] == "POST api.stripe.com/v1/payment_intents → 400 idempotency_error"
    assert lines[2].startswith("✅ verified:server:prod · Reusing an Idempotency-Key")
    assert lines[3] == "   fix: Set parameter Idempotency-Key to new UUID per distinct request"
    request = posted(server)
    assert request.get_json()["target"] == {
        "method": "POST",
        "url": "https://api.stripe.com/v1/payment_intents",
    }
    raw = request.get_data(as_text=True)
    assert SECRET not in raw and "expand" not in raw
    assert request.headers["User-Agent"].startswith("agentfacts-cli/")


def test_check_body_from_stdin(server):
    server.expect_request("/v0/check").respond_with_json(answer())
    result = runner.invoke(
        app, ["check", URL, "-X", "POST", "--status", "400", "--body", "-"], input="rate limited\n"
    )
    assert result.exit_code == 0, result.output
    assert posted(server).get_json()["error"] == {"status": 400, "body_excerpt": "rate limited\n"}


def test_non_utf8_stdin_body_is_an_excerpt(server):
    server.expect_request("/v0/check").respond_with_json(answer())
    result = runner.invoke(
        app, ["check", URL, "-X", "POST", "--body", "-"], input=b"erreur \xe9chou\xe9e"
    )
    assert result.exit_code == 0, result.output
    assert posted(server).get_json()["error"]["body_excerpt"] == "erreur \ufffdchou\ufffde"


def test_json_prints_the_raw_answer(server):
    server.expect_request("/v0/check").respond_with_json(answer())
    result = runner.invoke(app, ["check", URL, "-X", "POST", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == answer()


@pytest.mark.parametrize("target", ["pypi:stripe@12.1.0", "npm:@slack/web-api", "api.stripe.com"])
def test_locators_and_hosts_are_sent_verbatim(server, target):
    server.expect_request("/v0/check").respond_with_json(
        {"facts": [], "unknown": {"reason": "no_fact_for_signal"}}
    )
    result = runner.invoke(app, ["check", target])
    assert result.exit_code == 0, result.output
    assert posted(server).get_json() == {"target": {"url": target}}
    assert result.stdout.splitlines()[1:] == [target, "no known facts (no_fact_for_signal)"]


@pytest.mark.parametrize(
    "args",
    [
        ["not a url"],
        ["ftp://api.stripe.com/x"],
        [URL, "-X", "BREW"],
        [URL, "--status", "42"],
        [URL, "-X", "POST", "--body", "/nonexistent/body.txt"],
        [URL, "--status", "400"],
    ],
    ids=["not-a-target", "ftp", "method", "status", "body-file", "no-method-for-path"],
)
def test_usage_errors_exit_2_and_send_nothing(server, args):
    result = runner.invoke(app, ["check", *args])
    assert result.exit_code == 2, result.output
    assert server.log == []


def test_unreachable_registry_exits_1(env):
    env.setenv("AGENTFACTS_ENDPOINT", "http://127.0.0.1:9")
    result = runner.invoke(app, ["check", URL, "-X", "POST", "--status", "400"])
    assert result.exit_code == 1
    assert result.stderr.startswith("error: registry did not answer")


def test_disabled_refuses_the_network(server, env):
    server.expect_request("/v0/check").respond_with_json(answer())
    env.setenv("AGENTFACTS_DISABLE", "1")
    result = runner.invoke(app, ["check", URL, "-X", "POST"])
    assert result.exit_code == 1
    assert "AGENTFACTS_DISABLE" in result.stderr
    assert server.log == []


def test_offline_uses_the_snapshot(env, tmp_path):
    root = tmp_path / "snapshot"
    (root / "services").mkdir(parents=True)
    (root / "facts" / "stripe").mkdir(parents=True)
    shutil.copy(VALID / "service-stripe.yaml", root / "services" / "stripe.yaml")
    shutil.copy(VALID / FACT_FILE, root / "facts" / "stripe" / FACT_FILE)
    env.setenv("AGENTFACTS_ENDPOINT", "http://127.0.0.1:9")
    env.setenv("AGENTFACTS_SNAPSHOT", str(root))
    result = runner.invoke(app, ["check", URL, "-X", "POST", "--status", "400", "--offline"])
    assert result.exit_code == 0, result.output
    assert "fix: Set parameter Idempotency-Key to new UUID per distinct request" in result.stdout


def test_help_lists_check():
    result = runner.invoke(app, ["--help"])
    assert "check" in result.stdout
