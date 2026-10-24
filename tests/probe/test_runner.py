"""One tick end to end against a local `httpserver` (spec 04 Done when). No real network."""

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from probe_builders import FAKE_KEY
from werkzeug import Response

from agentfacts.probe import USER_AGENT
from agentfacts.probe.runner import TickOptions, kill_reason, run_tick
from agentfacts.schema.yamlio import load_yaml, plain

T0 = datetime(2026, 10, 20, 10, 0, 0, tzinfo=UTC)


class Clock:
    def __init__(self, at=T0):
        self.at = at

    def __call__(self):
        return self.at

    def advance(self, seconds):
        self.at += timedelta(seconds=seconds)


def tick(repo, httpserver, *, clock=None, environ=None, sleeps=None, **options):
    return run_tick(
        repo.root,
        repo.state,
        TickOptions(**options),
        keys_dir=repo.keys,
        base_urls={"acme": httpserver.url_for("")},
        sleep=(sleeps if sleeps is not None else []).append,
        clock=clock or Clock(),
        environ=environ or {},
    )


def fact(repo, slug="items-list-ok"):
    return plain(load_yaml(repo.root / "facts" / "acme" / f"{slug}.yaml"))


def outcomes(report):
    return {line.probe_id.split(":")[-1]: line.outcome for line in report.lines}


def test_two_step_probe_with_reference_and_sleep_confirms_the_fact(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe(
        steps=[
            {"do": "http", "method": "GET", "path": "/v1/items"},
            {"do": "sleep", "seconds": 0.5},
            {"do": "http", "method": "GET", "path": "/v1/items/{{step[1].json.data[0].id}}",
             "headers": {"Idempotency-Key": "{{run_uuid}}"}},
        ],
        **{"assert": [
            {"step": 1, "status": 200},
            {"step": 3, "json_path": "$.id", "equals": "it_1"},
            {"step": 3, "header": "Retry-After", "equals": "7"},
        ]},
    )
    repo.fact()
    httpserver.expect_request("/v1/items").respond_with_json(
        {"data": [{"id": "it_1"}]}, headers={"Set-Cookie": "s=1", "X-Other": "no"})
    httpserver.expect_request("/v1/items/it_1").respond_with_json(
        {"id": "it_1"}, headers={"Retry-After": "7"})
    sleeps = []

    report = tick(repo, httpserver, sleeps=sleeps)

    assert report.ok and outcomes(report) == {"items-list": "pass"}
    assert sleeps == [0.5]
    sent = [req for req, _ in httpserver.log]
    assert [r.path for r in sent] == ["/v1/items", "/v1/items/it_1"]
    assert all(r.headers["Authorization"] == f"Bearer {FAKE_KEY}" for r in sent)
    assert all(r.headers["User-Agent"] == USER_AGENT for r in sent)

    [line] = repo.results()
    assert {"probe_id", "vantage", "env", "started", "outcome", "steps", "asserts", "facts"} <= set(
        line)
    assert (line["probe_id"], line["vantage"], line["env"], line["outcome"]) == (
        "af:acme:probe:items-list", "illouminus", "sandbox", "pass")
    assert line["selection"] == "due"
    assert line["started"] == "2026-10-20T10:00:00Z"
    assert [s["do"] for s in line["steps"]] == ["http", "sleep", "http"]
    first, _, third = line["steps"]
    assert first["status"] == 200 and first["template"] == "/v1/items"
    assert set(first["headers"]) == {"content-type"}  # whitelist: no set-cookie, no x-other
    assert third["path"] == "/v1/items/it_1" and third["headers"]["retry-after"] == "7"
    assert len(third["body_fingerprint"]) == 64 and third["latency_ms"] >= 0
    assert [a["ok"] for a in line["asserts"]] == [True, True, True]
    assert line["facts"] == [{"id": "af:acme:items-list-ok", "change": "confirmed"}]

    ev = fact(repo)["evidence"]
    assert ev["confirmations"] == 2 and ev["stale_counter"] == 0
    assert ev["last_confirmed"] == "2026-10-20T10:00:00Z"


def test_three_failed_runs_make_the_fact_stale(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe()
    repo.fact()
    httpserver.expect_request("/v1/items").respond_with_json({"error": "gone"}, status=404)
    clock = Clock()
    for _ in range(3):
        report = tick(repo, httpserver, clock=clock)
        assert outcomes(report) == {"items-list": "fail"}
        clock.advance(300)
    assert fact(repo)["status"] == "stale"
    assert [line["facts"][0]["change"] for line in repo.results()] == ["failed", "failed", "stale"]
    assert repo.results()[0]["steps"][0]["error_string"] == "gone"


def test_unexpected_429_is_an_error_and_not_evidence(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe(steps=[{"do": "http", "method": "GET", "path": "/v1/items"},
                      {"do": "http", "method": "GET", "path": "/v1/items/x"}])
    path = repo.fact()
    before = path.read_bytes()
    httpserver.expect_request("/v1/items").respond_with_json({}, status=429)
    report = tick(repo, httpserver)
    assert outcomes(report) == {"items-list": "error"}
    assert "429" in report.lines[0].detail
    assert len(httpserver.log) == 1  # later steps are not sent
    assert path.read_bytes() == before
    assert repo.results()[0]["asserts"] == [] and repo.results()[0]["facts"] == []


def test_expected_429_is_asserted_normally(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe(steps=[{"do": "http", "method": "GET", "path": "/v1/items",
                       "expect_rate_limit": True}],
               **{"assert": [{"step": 1, "status": 429}, {"step": 1, "header": "Retry-After",
                                                          "present": True}]})
    repo.fact()
    httpserver.expect_request("/v1/items").respond_with_json({}, status=429,
                                                             headers={"Retry-After": "1"})
    assert outcomes(tick(repo, httpserver)) == {"items-list": "pass"}
    assert fact(repo)["evidence"]["confirmations"] == 2


def test_transport_error_is_not_evidence(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe()
    path = repo.fact()
    before = path.read_bytes()
    report = run_tick(repo.root, repo.state, TickOptions(timeout_s=1), keys_dir=repo.keys,
                      base_urls={"acme": "http://127.0.0.1:9"}, sleep=lambda s: None,
                      clock=Clock(), environ={})
    assert outcomes(report) == {"items-list": "error"}
    assert report.lines[0].detail == "step 1: connect_error"
    assert path.read_bytes() == before


def test_missing_key_skips_keyed_probes_without_error(repo, httpserver):
    repo.service()
    repo.probe()
    repo.probe("open", steps=[{"do": "http", "method": "GET", "path": "/v1/items/x",
                               "auth": "none"}])
    httpserver.expect_request("/v1/items/x").respond_with_json({})
    report = tick(repo, httpserver)
    assert report.ok
    assert outcomes(report) == {"items-list": "skipped:no_key", "open": "pass"}
    assert [r.path for r, _ in httpserver.log] == ["/v1/items/x"]
    assert "Authorization" not in httpserver.log[0][0].headers
    assert {line["outcome"] for line in repo.results()} == {"skipped:no_key", "pass"}


def test_skipped_probe_waits_a_budget_but_uses_no_template(repo, httpserver):
    repo.service()
    repo.probe()
    repo.probe("open", steps=[{"do": "http", "method": "GET", "path": "/v1/items",
                               "auth": "none"}])
    httpserver.expect_request("/v1/items").respond_with_json({})
    clock = Clock()
    report = tick(repo, httpserver, clock=clock)
    assert outcomes(report) == {"items-list": "skipped:no_key", "open": "pass"}
    clock.advance(10)
    assert outcomes(tick(repo, httpserver, clock=clock)) == {}


def test_kill_switch_file_stops_before_any_request(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe()
    (repo.root / "ops").mkdir()
    (repo.root / "ops" / "KILL").write_text("")
    report = tick(repo, httpserver)
    assert report.killed == "ops/KILL" and report.lines == []
    assert httpserver.log == [] and not repo.state.exists()


def test_kill_switch_env_stops_before_any_request(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe()
    report = tick(repo, httpserver, environ={"AGENTFACTS_KILL": "1"})
    assert report.killed == "AGENTFACTS_KILL=1"
    assert httpserver.log == [] and not repo.state.exists()
    assert kill_reason(repo.root, {"AGENTFACTS_KILL": "0"}) is None


def test_kill_switch_mid_tick_stops_the_remaining_probes(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe("a-first")
    repo.probe("b-second", steps=[{"do": "http", "method": "GET", "path": "/v1/items/x"}])

    def kill_then_answer(request):
        (repo.root / "ops").mkdir(exist_ok=True)
        (repo.root / "ops" / "KILL").write_text("")
        return Response("{}", 200, content_type="application/json")

    httpserver.expect_request("/v1/items").respond_with_handler(kill_then_answer)
    report = tick(repo, httpserver)
    assert outcomes(report) == {"a-first": "pass"} and report.killed == "ops/KILL"
    assert len(httpserver.log) == 1


def test_max_probes_per_tick(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe("a-first")
    repo.probe("b-second", steps=[{"do": "http", "method": "GET", "path": "/v1/items/x"}])
    httpserver.expect_request("/v1/items").respond_with_json({})
    httpserver.expect_request("/v1/items/x").respond_with_json({})
    report = tick(repo, httpserver, max_probes=1)
    assert outcomes(report) == {"a-first": "pass"}
    assert report.counts["deferred"] == 1


def test_max_requests_defers_a_probe_that_does_not_fit(repo, httpserver):
    repo.service()
    repo.key()
    two = [{"do": "http", "method": "GET", "path": "/v1/items"},
           {"do": "http", "method": "GET", "path": "/v1/items/x"}]
    repo.probe("a-two-requests", steps=two)
    repo.probe("b-one-request", steps=[{"do": "http", "method": "GET", "path": "/v1/redirect"}])
    httpserver.expect_request("/v1/items").respond_with_json({})
    httpserver.expect_request("/v1/items/x").respond_with_json({})
    httpserver.expect_request("/v1/redirect").respond_with_json({})
    report = tick(repo, httpserver, max_requests=1)
    assert outcomes(report) == {"b-one-request": "pass"}
    assert report.counts["deferred"] == 1


def test_budget_between_ticks_and_run_all(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe()
    httpserver.expect_request("/v1/items").respond_with_json({})
    clock = Clock()
    assert outcomes(tick(repo, httpserver, clock=clock)) == {"items-list": "pass"}
    clock.advance(299)
    report = tick(repo, httpserver, clock=clock)
    assert outcomes(report) == {} and report.counts["not_due"] == 1
    assert outcomes(tick(repo, httpserver, clock=clock, run_all=True)) == {"items-list": "pass"}
    clock.advance(300)
    assert outcomes(tick(repo, httpserver, clock=clock)) == {"items-list": "pass"}
    assert len(httpserver.log) == 3
    # the digest tells a budget violation from a deliberate --all by this field
    assert [r["selection"] for r in repo.results()] == ["due", "all", "due"]


def test_service_budget_override(repo, httpserver):
    repo.service(probe_budget={"per_template_seconds": 900})
    repo.key()
    repo.probe()
    httpserver.expect_request("/v1/items").respond_with_json({})
    clock = Clock()
    tick(repo, httpserver, clock=clock)
    clock.advance(600)
    assert outcomes(tick(repo, httpserver, clock=clock)) == {}


def test_two_probes_on_one_template_do_not_double_the_rate(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe("a-first")
    repo.probe("b-same-template")
    httpserver.expect_request("/v1/items").respond_with_json({})
    clock = Clock()
    assert outcomes(tick(repo, httpserver, clock=clock)) == {"a-first": "pass"}
    clock.advance(300)
    assert outcomes(tick(repo, httpserver, clock=clock)) == {"b-same-template": "pass"}


def test_oldest_probe_runs_first(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe("a-first")
    repo.probe("b-second", steps=[{"do": "http", "method": "GET", "path": "/v1/items/x"}])
    httpserver.expect_request("/v1/items").respond_with_json({})
    httpserver.expect_request("/v1/items/x").respond_with_json({})
    clock = Clock()
    assert outcomes(tick(repo, httpserver, clock=clock, max_probes=1)) == {"a-first": "pass"}
    clock.advance(300)
    assert outcomes(tick(repo, httpserver, clock=clock, max_probes=1)) == {"b-second": "pass"}


def test_redaction_keeps_the_key_out_of_every_output(repo, httpserver, capsys):
    repo.service()
    repo.key()
    repo.probe(**{"assert": [{"step": 1, "status": 200}]})
    repo.fact()

    def echo(request):
        token = request.headers["Authorization"]
        body = {"error": {"message": f"bad token {token} / {FAKE_KEY}"}}
        return Response(json.dumps(body), 401, {"X-Echo": FAKE_KEY, "Retry-After": token},
                        content_type="application/json")

    httpserver.expect_request("/v1/items").respond_with_handler(echo)
    report = tick(repo, httpserver)
    assert outcomes(report) == {"items-list": "fail"}
    line = repo.results()[0]
    assert line["steps"][0]["headers"]["x-echo"] == "[redacted]"  # whitelisted, then redacted
    for path in [*repo.state.rglob("*"), *(repo.root / "facts").rglob("*")]:
        if path.is_file():
            assert FAKE_KEY.encode() not in path.read_bytes(), path
    rendered = " ".join(f"{x.probe_id} {x.outcome} {x.detail}" for x in report.lines)
    assert FAKE_KEY not in rendered and FAKE_KEY not in capsys.readouterr().out


def test_a_different_env_never_refutes(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe()  # env sandbox
    prod_fact = repo.fact("items-list-prod", env="prod")
    before = prod_fact.read_bytes()
    httpserver.expect_request("/v1/items").respond_with_json({}, status=404)
    clock = Clock()
    for _ in range(4):
        assert outcomes(tick(repo, httpserver, clock=clock)) == {"items-list": "fail"}
        clock.advance(300)
    assert prod_fact.read_bytes() == before
    assert {line["facts"][0]["change"] for line in repo.results()} == {"other_dimension"}


def test_refused_rendered_request_is_an_error_and_a_problem(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe(steps=[
        {"do": "http", "method": "GET", "path": "/v1/items"},
        {"do": "http", "method": "GET", "path": "/v1/items/{{step[1].json.id}}"},
    ])
    path = repo.fact()
    before = path.read_bytes()
    httpserver.expect_request("/v1/items").respond_with_json({"id": ".."})
    report = tick(repo, httpserver)
    assert outcomes(report) == {"items-list": "error"}
    assert report.lines[0].detail.startswith("refused:template_error")
    assert not report.ok and len(httpserver.log) == 1
    assert path.read_bytes() == before


def unvalidated(monkeypatch, service_overrides, probe_overrides=None):
    """Bypass the loader's validator gate to reach the runner's own run-time refusals."""
    from probe_builders import make_service, probe_doc

    import agentfacts.probe.runner as runner_module
    from agentfacts.probe.loader import LoadedProbe
    from agentfacts.probe.loader import Repo as LoadedRepo
    from agentfacts.schema.models import Probe

    service = make_service(**service_overrides)
    probe = Probe.model_validate(probe_doc(**(probe_overrides or {})))
    loaded = LoadedRepo(services={"acme": service}, probes=[LoadedProbe(Path("p.yaml"), probe)])
    monkeypatch.setattr(runner_module, "load_repo", lambda root: loaded)


def test_foreign_base_url_is_rejected_by_the_validator(repo, httpserver):
    repo.service(dimensions={"env": {"sandbox": "https://evil.example.org"}})
    repo.key()
    repo.probe()
    report = run_tick(repo.root, repo.state, TickOptions(), keys_dir=repo.keys,
                      sleep=lambda s: None, clock=Clock(), environ={})
    assert not report.ok and report.lines == []
    assert {p.code for p in report.problems} == {"foreign_env_url", "unknown_service"}


def test_foreign_base_url_is_refused_at_run_time_too(repo, httpserver, monkeypatch):
    unvalidated(monkeypatch, {"dimensions": {"env": {"sandbox": "https://evil.example.org"}}})
    repo.key()
    report = run_tick(repo.root, repo.state, TickOptions(), keys_dir=repo.keys,
                      sleep=lambda s: None, clock=Clock(), environ={})
    assert report.refused == ["af:acme:probe:items-list"] and not report.ok
    assert report.lines[0].detail.startswith("refused:foreign_host")
    assert httpserver.log == []


def test_invalid_probe_file_is_a_problem_but_others_run(repo, httpserver):
    repo.service(auth={"kind": "none"})
    repo.probe("write-in-prod", env="prod",
               steps=[{"do": "http", "method": "POST", "path": "/v1/items"}])
    repo.probe("fine", env="sandbox")
    httpserver.expect_request("/v1/items").respond_with_json({})
    report = tick(repo, httpserver)
    assert outcomes(report) == {"fine": "pass"}
    assert not report.ok and {p.code for p in report.problems} == {"prod_probe_not_readonly"}
    assert [r.method for r, _ in httpserver.log] == ["GET"]


def test_dry_run_sends_nothing_and_writes_nothing(repo, httpserver):
    repo.service()
    repo.probe()
    repo.probe("open", steps=[{"do": "http", "method": "GET", "path": "/v1/items/x",
                               "auth": "none"}])
    path = repo.fact()
    before = path.read_bytes()
    report = tick(repo, httpserver, dry_run=True)
    assert outcomes(report) == {"items-list": "skipped:no_key", "open": "would-run"}
    assert httpserver.log == [] and not repo.state.exists()
    assert path.read_bytes() == before


def test_dry_run_reports_not_due_and_deferred(repo, httpserver):
    repo.service(auth={"kind": "none"})
    repo.probe("a-first")
    repo.probe("b-same-template")
    repo.probe("c-other", steps=[{"do": "http", "method": "GET", "path": "/v1/items/x"}])
    report = tick(repo, httpserver, dry_run=True, max_probes=1)
    assert outcomes(report) == {"a-first": "would-run", "b-same-template": "not-due",
                                "c-other": "deferred"}


def test_vantage_is_recorded_and_budgeted_separately(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe()
    path = repo.fact()
    httpserver.expect_request("/v1/items").respond_with_json({})
    clock = Clock()
    tick(repo, httpserver, clock=clock)
    report = tick(repo, httpserver, clock=clock, vantage="freebox")
    assert outcomes(report) == {"items-list": "pass"}
    assert repo.results()[-1]["vantage"] == "freebox"
    assert plain(load_yaml(path))["evidence"]["vantages"] == ["illouminus", "freebox"]


def test_no_llm_client_is_imported_by_the_runner():
    banned = ("openai", "anthropic", "google.genai", "google.generativeai")
    package = Path(__file__).parents[2] / "agentfacts" / "probe"
    for source in package.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(banned), f"{source.name} imports {name}"


def test_secret_is_redacted_before_truncation_and_normalization(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe(**{"assert": [{"step": 1, "json_path": "$.error.message", "equals": "x"}]})
    padding = "p " * 250  # pushes the key across the 512-char error cap
    httpserver.expect_request("/v1/items").respond_with_json(
        {"error": {"message": padding + FAKE_KEY + " tail"}}, status=400)
    tick(repo, httpserver)
    raw = (repo.state / "results.jsonl").read_text()
    for fragment in (FAKE_KEY, FAKE_KEY.lower(), FAKE_KEY[:12], FAKE_KEY.lower()[:12]):
        assert fragment not in raw, fragment


def test_key_must_be_named_after_its_service(repo, httpserver, monkeypatch):
    repo.service(auth={"kind": "bearer", "key_name": "stripe-test", "env": "sandbox"})
    repo.probe()
    assert {p.code for p in tick(repo, httpserver).problems} == {"key_not_bound", "unknown_service"}

    unvalidated(monkeypatch, {"auth": {"kind": "bearer", "key_name": "stripe-test",
                                       "env": "sandbox"}})
    repo.key("stripe-test")
    report = tick(repo, httpserver)
    assert outcomes(report) == {"items-list": "error"}
    assert report.lines[0].detail.startswith("refused:key_not_bound")
    assert report.refused == ["af:acme:probe:items-list"] and not report.ok
    assert httpserver.log == []
    dry = tick(repo, httpserver, dry_run=True, run_all=True)
    assert outcomes(dry) == {"items-list": "refused"}


def test_key_named_after_the_service_is_accepted(repo, httpserver):
    for name in ("acme", "acme-live", "acme_test"):
        repo.service(auth={"kind": "bearer", "key_name": name, "env": "sandbox"})
        repo.key(name)
        repo.probe()
        httpserver.expect_request("/v1/items").respond_with_json({})
        assert outcomes(tick(repo, httpserver, run_all=True)) == {"items-list": "pass"}, name


def test_a_prefix_without_separator_is_not_the_service(repo, httpserver, monkeypatch):
    unvalidated(monkeypatch, {"auth": {"kind": "bearer", "key_name": "acmecorp-test",
                                       "env": "sandbox"}})
    repo.key("acmecorp-test")
    assert outcomes(tick(repo, httpserver)) == {"items-list": "error"}
    assert httpserver.log == []


def test_unexpected_5xx_is_an_error_and_not_evidence(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe()
    path = repo.fact()
    before = path.read_bytes()
    httpserver.expect_request("/v1/items").respond_with_json({"error": "down"}, status=503)
    report = tick(repo, httpserver)
    assert outcomes(report) == {"items-list": "error"}
    assert report.lines[0].detail == "step 1: server error (503)"
    assert path.read_bytes() == before and report.ok


def test_asserted_5xx_is_evidence(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe(**{"assert": [{"step": 1, "status": 503}]})
    repo.fact()
    httpserver.expect_request("/v1/items").respond_with_json({}, status=503)
    assert outcomes(tick(repo, httpserver)) == {"items-list": "pass"}


def test_a_bad_header_value_refuses_one_probe_not_the_tick(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe("a-first", steps=[
        {"do": "http", "method": "GET", "path": "/v1/items"},
        {"do": "http", "method": "GET", "path": "/v1/items/x",
         "headers": {"X-Ref": "{{step[1].json.name}}"}},
    ])
    repo.probe("b-second", steps=[{"do": "http", "method": "GET", "path": "/v1/redirect"}])
    httpserver.expect_request("/v1/items").respond_with_json({"name": "caf\u00e9"})
    httpserver.expect_request("/v1/redirect").respond_with_json({})
    report = tick(repo, httpserver)
    assert outcomes(report) == {"a-first": "error", "b-second": "pass"}
    assert report.lines[0].detail.startswith("refused:invalid_header")


def test_a_second_tick_waits_for_the_running_one(repo, httpserver):
    import fcntl

    repo.service()
    repo.key()
    repo.probe()
    repo.state.mkdir(parents=True)
    with (repo.state / "probe.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = tick(repo, httpserver)
    assert report.busy and report.lines == [] and httpserver.log == []
    assert not (repo.state / "results.jsonl").exists()
    httpserver.expect_request("/v1/items").respond_with_json({})
    assert outcomes(tick(repo, httpserver)) == {"items-list": "pass"}


def test_dry_run_never_reads_a_key(repo, httpserver, monkeypatch):
    import agentfacts.probe.runner as runner_module

    repo.service()
    repo.key()
    repo.probe()

    def no_read(*args):
        raise AssertionError("dry run read a key")

    import agentfacts.probe.keys as keys_module

    monkeypatch.setattr(runner_module, "read_key", no_read)
    monkeypatch.setattr(keys_module, "read_key", no_read)
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (
        no_read() if self.suffix == ".key" else Path.read_bytes(self).decode()))
    assert outcomes(tick(repo, httpserver, dry_run=True)) == {"items-list": "would-run"}


def test_dry_run_counts(repo, httpserver):
    repo.service(auth={"kind": "none"})
    repo.probe("a-first")
    repo.probe("b-same-template")
    report = tick(repo, httpserver, dry_run=True)
    assert dict(report.counts) == {"would_run": 1, "not_due": 1}


def test_details_are_clipped_after_redaction(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe(**{"assert": [{"step": 1, "json_path": "$.msg", "equals": "x"}]})
    httpserver.expect_request("/v1/items").respond_with_json({"msg": "m" * 5000})
    tick(repo, httpserver)
    line = repo.results()[0]
    assert len(line["asserts"][0]["detail"]) <= 200 and len(line["detail"]) <= 200


def test_a_top_level_description_is_the_error_string(repo, httpserver):
    """Telegram's error shape: {ok: false, error_code, description} (check() reads it too)."""
    repo.service()
    repo.key()
    repo.probe()
    body = {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}
    httpserver.expect_request("/v1/items").respond_with_json(body, status=400)
    tick(repo, httpserver)
    step = repo.results()[0]["steps"][0]
    assert step["error_string"] == "Bad Request: chat not found"
    assert step["normalized"] == "bad request: chat not found"
