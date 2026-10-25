import importlib.metadata
import json

import pytest
from werkzeug import Response

from conftest import answer, requests_to

STRIPE_TEST = """
import requests

BODY = (
    b'{"error": {"code": "idempotency_error", "message": "Keys for idempotent requests can only '
    b'be used with the same parameters they were first used with. key sk_test_abcdefgh12345678", '
    b'"type": "invalid_request_error"}}'
)


def stripe_error():
    response = requests.Response()
    response.status_code = 400
    response._content = BODY
    response.url = "https://api.stripe.com/v1/payment_intents?expand[]=customer&key=q1w2e3r4"
    response.request = requests.Request(
        "POST", response.url,
        data={"amount": "100", "card": "4242424242424242"},
        headers={"Authorization": "Bearer sk_live_SECRETSECRET123", "Cookie": "sid=abc"},
    ).prepare()
    return response


def test_create_payment_intent():
    stripe_error().raise_for_status()
"""

SECTION = [
    "*─ Known facts (apifacts, CC BY 4.0) ─*",
    "POST api.stripe.com/v1/payment_intents → 400 idempotency_error",
    "✅ verified:server:prod · Reusing an Idempotency-Key with a different request body *",
    "   fix: Set parameter Idempotency-Key to new UUID per distinct request",
    "   https://github.com/Illouminus/apifacts/blob/main/pages/stripe/"
    "idempotency-key-reuse-different-params.md",
]


@pytest.fixture
def serve_check(registry):
    def serve(response=None):
        handler = registry.expect_request("/v0/check", method="POST")
        if response is None:
            handler.respond_with_json(answer())
        else:
            handler.respond_with_response(response)
        return registry

    return serve


def assert_untouched(result, failed=1):
    result.assert_outcomes(failed=failed)
    assert "INTERNALERROR" not in result.stdout.str()
    assert "Known facts" not in result.stdout.str()


def test_failing_http_test_prints_known_facts(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile(STRIPE_TEST)
    result = pytester.runpytest()
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(SECTION)
    assert len(requests_to(server, "/v0/services")) == 1
    assert len(requests_to(server, "/v0/check")) == 1


def test_only_safe_fields_are_sent(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile(STRIPE_TEST)
    pytester.runpytest()
    (request,) = requests_to(server, "/v0/check")
    body = request.get_json()
    assert set(body) <= {"target", "error", "context"}
    assert body["target"] == {"method": "POST", "url": "https://api.stripe.com/v1/payment_intents"}
    assert body["error"]["status"] == 400
    assert "Keys for idempotent requests" in body["error"]["body_excerpt"]
    raw = request.get_data(as_text=True)
    for leaked in (
        "sk_live",
        "sk_test_abcdefgh",
        "4242",
        "amount",
        "Bearer",
        "Cookie",
        "sid=",
        "expand",
        "q1w2e3r4",
    ):
        assert leaked not in raw, leaked
    assert request.headers["User-Agent"].startswith("apifacts-pytest/0.1.0 ")
    assert "Authorization" not in request.headers and "Cookie" not in request.headers


def test_httpx_error_prints_known_facts(pytester, serve_check):
    serve_check()
    pytester.makepyfile(
        """
        import httpx

        def test_create():
            request = httpx.Request("POST", "https://api.stripe.com/v1/payment_intents")
            httpx.Response(400, request=request, json={"error": {"code": "idempotency_error"}}
                           ).raise_for_status()
        """
    )
    result = pytester.runpytest()
    result.stdout.fnmatch_lines(SECTION)


def test_url_with_path_but_no_method_sends_nothing(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile(
        """
        import types

        def test_sdk():
            exc = Exception("bad request")
            exc.status_code = 400
            exc.request = types.SimpleNamespace(url="https://api.stripe.com/v1/payment_intents")
            raise exc
        """
    )
    assert_untouched(pytester.runpytest())
    assert requests_to(server, "/v0/check") == []


def test_passing_tests_send_nothing(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile("def test_ok():\n    assert True\n")
    pytester.runpytest().assert_outcomes(passed=1)
    assert server.log == []


def test_non_http_failures_send_nothing(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile("def test_bad():\n    assert 1 == 2\n")
    assert_untouched(pytester.runpytest())
    assert server.log == []


def test_host_not_in_registry_sends_no_check(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile(
        """
        import httpx

        def test_github():
            request = httpx.Request("GET", "https://api.github.com/user")
            httpx.Response(401, request=request, text="Bad credentials").raise_for_status()
        """
    )
    assert_untouched(pytester.runpytest())
    assert len(requests_to(server, "/v0/services")) == 1
    assert requests_to(server, "/v0/check") == []


def test_opt_out_sends_nothing(pytester, serve_check, plugin_env):
    server = serve_check()
    plugin_env.setenv("APIFACTS_DISABLE", "1")
    pytester.makepyfile(STRIPE_TEST)
    assert_untouched(pytester.runpytest())
    assert server.log == []


def test_disabled_with_p_no(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile(STRIPE_TEST)
    assert_untouched(pytester.runpytest("-p", "no:apifacts"))
    assert server.log == []


@pytest.mark.parametrize(
    "response",
    [
        Response("boom", status=500),
        Response("{not json", status=200, content_type="application/json"),
        Response(
            json.dumps({"facts": "nope", "matched_template": 3}),
            status=200,
            content_type="application/json",
        ),
        Response(
            json.dumps({"facts": [{"claim": None, "fixes": "x"}, 7]}),
            status=200,
            content_type="application/json",
        ),
    ],
    ids=["500", "garbage", "wrong-types", "broken-facts"],
)
def test_server_failure_never_breaks_the_run(pytester, serve_check, response):
    serve_check(response)
    pytester.makepyfile(STRIPE_TEST)
    assert_untouched(pytester.runpytest())


def test_unreachable_registry_never_breaks_the_run(pytester, plugin_env):
    plugin_env.setenv("APIFACTS_ENDPOINT", "http://127.0.0.1:9")
    pytester.makepyfile(STRIPE_TEST)
    assert_untouched(pytester.runpytest())


def test_services_failure_sends_no_check(pytester, httpserver, plugin_env):
    plugin_env.setenv("APIFACTS_ENDPOINT", httpserver.url_for("").rstrip("/"))
    httpserver.expect_request("/v0/services").respond_with_data("down", status=503)
    pytester.makepyfile(STRIPE_TEST)
    assert_untouched(pytester.runpytest())
    assert requests_to(httpserver, "/v0/check") == []


def test_same_error_twice_is_checked_once(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile(
        STRIPE_TEST + "\n\ndef test_again():\n    stripe_error().raise_for_status()\n"
    )
    result = pytester.runpytest()
    result.assert_outcomes(failed=2)
    assert result.stdout.str().count("Known facts (apifacts, CC BY 4.0)") == 2
    assert len(requests_to(server, "/v0/check")) == 1


def test_services_list_is_cached_between_runs(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile(STRIPE_TEST)
    pytester.runpytest()
    pytester.runpytest()
    assert len(requests_to(server, "/v0/services")) == 1
    assert len(requests_to(server, "/v0/check")) == 2


def test_setup_errors_are_annotated(pytester, serve_check):
    serve_check()
    pytester.makepyfile(
        STRIPE_TEST.replace("def test_create_payment_intent", "def _unused")
        + "\n\nimport pytest\n\n@pytest.fixture\ndef customer():\n"
        "    stripe_error().raise_for_status()\n\ndef test_uses(customer):\n    pass\n"
    )
    result = pytester.runpytest()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(SECTION)


def test_xfail_sends_nothing(pytester, serve_check):
    server = serve_check()
    pytester.makepyfile(
        STRIPE_TEST.replace("def test_create", "@pytest.mark.xfail\ndef test_create").replace(
            "import requests", "import pytest\nimport requests"
        )
    )
    pytester.runpytest().assert_outcomes(xfailed=1)
    assert server.log == []


def test_section_reaches_junit_xml(pytester, serve_check):
    serve_check()
    pytester.makepyfile(STRIPE_TEST)
    pytester.runpytest("--junitxml=report.xml")
    xml = (pytester.path / "report.xml").read_text()
    assert "Known facts (apifacts, CC BY 4.0)" in xml
    assert "Set parameter Idempotency-Key to new UUID per distinct request" in xml


def test_section_shown_with_show_capture_no(pytester, serve_check):
    serve_check()
    pytester.makepyfile(STRIPE_TEST)
    pytester.runpytest("--show-capture=no").stdout.fnmatch_lines(SECTION)


def test_offline_answers_from_the_snapshot_without_network(pytester, plugin_env, snapshot_dir):
    plugin_env.setenv("APIFACTS_ENDPOINT", "http://127.0.0.1:9")
    plugin_env.setenv("APIFACTS_SNAPSHOT", str(snapshot_dir))
    pytester.makepyfile(STRIPE_TEST)
    result = pytester.runpytest("--apifacts-offline")
    result.stdout.fnmatch_lines(SECTION)


def test_offline_with_the_packaged_snapshot_is_silent(pytester, httpserver, plugin_env):
    plugin_env.setenv("APIFACTS_ENDPOINT", httpserver.url_for("").rstrip("/"))
    pytester.makepyfile(STRIPE_TEST)
    assert_untouched(pytester.runpytest("--apifacts-offline"))
    assert httpserver.log == []


def test_entry_point_is_named_apifacts():
    (entry,) = [
        e for e in importlib.metadata.entry_points(group="pytest11") if e.name == "apifacts"
    ]
    assert entry.value == "apifacts_pytest.plugin"


def test_explicit_p_apifacts_without_autoload(pytester, plugin_env, snapshot_dir):
    plugin_env.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    plugin_env.setenv("APIFACTS_SNAPSHOT", str(snapshot_dir))
    pytester.makepyfile(STRIPE_TEST)
    result = pytester.runpytest_subprocess("-p", "apifacts", "--apifacts-offline")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(SECTION)
