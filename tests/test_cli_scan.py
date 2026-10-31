import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apifacts.cli import app
from apifacts.schema.yamlio import load_yaml, plain

runner = CliRunner()
VALID = Path(__file__).parent / "fixtures" / "valid"
LOGS = Path(__file__).parent / "fixtures" / "logs"
FACT_FILE = "fact-idempotency-key-reuse-different-params.yaml"

# requests (no method; the snapshot knows only POST for this path), axios (method in the dump),
# a host the registry does not know, and a path with no registered template.
LOG = "\n".join(
    [
        "E   requests.exceptions.HTTPError: 400 Client Error: Bad Request for url: "
        "https://api.stripe.com/v1/payment_intents?key=sk_test_abcdefgh12345678",
        (LOGS / "axios.log").read_text(),
        "HTTP 404: Not Found (https://api.unknown-vendor.io/v2/things)",
        "HTTP 404: Not Found (https://api.stripe.com/v1/refunds)",
    ]
)


def answer(facts=True):
    fact = plain(load_yaml(VALID / FACT_FILE))
    return {
        "service": "stripe",
        "matched_template": {"method": "POST", "path": "/v1/payment_intents"},
        "facts": [fact] if facts else [],
        "registry": {"version": "2026-10-20", "license": "CC-BY-4.0"},
    }


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    for name in ("APIFACTS_DISABLE", "APIFACTS_ENDPOINT", "GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "snapshot"
    (root / "services").mkdir(parents=True)
    (root / "facts" / "stripe").mkdir(parents=True)
    shutil.copy(VALID / "service-stripe.yaml", root / "services" / "stripe.yaml")
    shutil.copy(VALID / FACT_FILE, root / "facts" / "stripe" / FACT_FILE)
    monkeypatch.setenv("APIFACTS_SNAPSHOT", str(root))
    return monkeypatch


@pytest.fixture
def server(httpserver, env):
    env.setenv("APIFACTS_ENDPOINT", httpserver.url_for("").rstrip("/"))
    httpserver.expect_request("/v0/services").respond_with_json(
        {"services": [{"key": "stripe", "hosts": ["api.stripe.com"], "instance_hosts": []}]}
    )
    return httpserver


def checks(httpserver):
    return [r.get_json() for r, _ in httpserver.log if r.path == "/v0/check"]


def scan(*args, input=LOG):
    return runner.invoke(app, ["scan", *args], input=input)


def test_scan_reports_stated_methods_and_preflights_inferred_ones(server):
    server.expect_request("/v0/check", method="POST").respond_with_json(answer())
    result = scan()
    assert result.exit_code == 0, result.output
    sent = checks(server)
    assert sent == [
        # no method in the log, POST is the only template: asked without the error (never stored)
        {"target": {"method": "POST", "url": "https://api.stripe.com/v1/payment_intents"}},
        # axios said POST: reported like the plugin reports it
        {
            "target": {"method": "POST", "url": "https://api.stripe.com/v1/customers"},
            "error": {
                "status": 401,
                "body_excerpt": "{ error: { message: 'Invalid API Key provided: sk_test_****5678',"
                " type: 'invalid_request_error' } }",
            },
        },
    ]
    raw = json.dumps(sent)
    assert "unknown-vendor" not in raw and "refunds" not in raw and "jane" not in raw
    out = result.stdout
    assert "POST api.stripe.com/v1/payment_intents → 400\n✅ verified:server:prod" in out
    assert "(method not in the log: POST is the only one registered for this path;" in out
    assert "api.stripe.com/v1/refunds → 404\n   (method not in the log; to look it up: " in out
    assert out.rstrip().splitlines()[-1] == (
        "apifacts scan: 4 failed HTTP calls in the log; 2 looked up, 1 with known facts;"
        " 1 to hosts the registry does not know (not sent); 1 without a method (not sent)"
    )
    assert "::warning" not in out  # not on GitHub, not asked for


def test_preflight_answer_keeps_only_facts_for_the_status(server):
    server.expect_request("/v0/check").respond_with_json(answer())
    log = (
        "E   requests.exceptions.HTTPError: 409 Client Error: Conflict for url: "
        "https://api.stripe.com/v1/payment_intents"
    )
    result = scan(input=log)
    assert result.exit_code == 0, result.output
    assert "POST api.stripe.com/v1/payment_intents → 409\nno known facts" in result.stdout


def test_github_annotations_and_step_summary(server, env, tmp_path):
    server.expect_request("/v0/check").respond_with_json(answer())
    summary = tmp_path / "summary.md"
    env.setenv("GITHUB_ACTIONS", "true")
    env.setenv("GITHUB_STEP_SUMMARY", str(summary))
    result = scan()
    assert result.exit_code == 0, result.output
    warnings = [line for line in result.stdout.splitlines() if line.startswith("::")]
    assert len(warnings) == 1  # the 401 has no fact for its status: log only
    assert warnings[0].startswith(
        "::warning title=apifacts%3A POST api.stripe.com/v1/payment_intents → 400::"
        "✅ verified:server:prod · Reusing an Idempotency-Key"
    )
    assert (
        "%0A   fix: Set parameter Idempotency-Key to new UUID per distinct request%0A"
        in (warnings[0])
    )
    md = summary.read_text()
    assert md.startswith("### Known facts (apifacts, CC BY 4.0)\n\napifacts scan: 4 failed")
    assert "```text\nPOST api.stripe.com/v1/payment_intents → 400\n" in md
    assert "api.stripe.com/v1/refunds → 404\n   (method not in the log" in md
    assert "unknown-vendor" not in md


def test_annotation_needs_a_fact_for_this_status(server, env, tmp_path):
    other = answer()
    other["facts"][0]["signal"]["status"] = 429  # a service-wide fact the cascade adds
    server.expect_request("/v0/check").respond_with_json(other)
    env.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    result = scan("--github")
    assert result.exit_code == 0
    assert "::warning" not in result.stdout
    assert "Reusing an Idempotency-Key" in result.stdout  # the log keeps the whole answer
    assert "Reusing" not in (tmp_path / "summary.md").read_text()


def test_json(server):
    server.expect_request("/v0/check").respond_with_json(answer())
    result = scan("--json", "--github")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)  # no annotation lines mixed in
    outcomes = [(c["source"], c["outcome"], c["method_source"]) for c in data["calls"]]
    assert outcomes == [
        ("requests", "facts", "registry"),
        ("axios", "no_facts", "log"),
        ("gh", "not_registered", None),
        ("gh", "method_unknown", None),
    ]
    assert all("?" not in c["url"] for c in data["calls"])


def test_max_lookups(server):
    server.expect_request("/v0/check").respond_with_json(answer())
    result = scan("--max-lookups", "1")
    assert result.exit_code == 0
    assert len(checks(server)) == 1
    assert "(not looked up: --max-lookups 1 reached)" in result.stdout


def test_registry_down_is_still_exit_0(env):
    env.setenv("APIFACTS_ENDPOINT", "http://127.0.0.1:9")
    result = scan()
    assert result.exit_code == 0
    assert "0 looked up" in result.stdout
    assert result.stderr.startswith("apifacts scan: ")


def test_disabled_sends_nothing(server, env):
    env.setenv("APIFACTS_DISABLE", "1")
    result = scan()
    assert result.exit_code == 0
    assert server.log == []
    assert "APIFACTS_DISABLE" in result.stderr


def test_nothing_found_writes_no_summary(server, env, tmp_path):
    summary = tmp_path / "summary.md"
    env.setenv("GITHUB_STEP_SUMMARY", str(summary))
    result = scan("--github", input="all 312 tests passed\n")
    assert result.exit_code == 0
    assert result.stdout.strip() == "apifacts scan: 0 failed HTTP calls in the log"
    assert not summary.exists() and server.log == []


def test_offline_from_a_file(env, tmp_path):
    env.setenv("APIFACTS_ENDPOINT", "http://127.0.0.1:9")
    log = tmp_path / "step.log"
    log.write_text(LOG)
    result = runner.invoke(app, ["scan", str(log), "--offline"])
    assert result.exit_code == 0, result.output
    assert "fix: Set parameter Idempotency-Key to new UUID per distinct request" in result.stdout


def test_only_the_tail_of_a_huge_log_is_read(server, tmp_path):
    from apifacts.client.logscan import MAX_LOG_BYTES

    server.expect_request("/v0/check").respond_with_json(answer())
    early = 'HTTP Request: POST https://api.stripe.com/v1/customers "HTTP/1.1 401 Unauthorized"\n'
    log = tmp_path / "big.log"
    log.write_text(early + "x" * MAX_LOG_BYTES + "\n")
    result = runner.invoke(app, ["scan", str(log)])
    assert result.exit_code == 0
    assert "0 failed HTTP calls" in result.stdout


def test_unreadable_file_is_a_usage_error(env):
    result = runner.invoke(app, ["scan", "/nonexistent/step.log"])
    assert result.exit_code == 2
