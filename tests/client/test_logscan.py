from pathlib import Path

import pytest

from apifacts.client.logscan import clean_lines, failures, scan

LOGS = Path(__file__).parent.parent / "fixtures" / "logs"


def found(name):
    return [
        (f.source, f.signal.method, f.signal.url, f.signal.status, f.signal.body_excerpt)
        for f in scan((LOGS / name).read_text())
    ]


def test_requests_http_error_once_query_dropped_localhost_skipped():
    # The traceback line and the short-summary line are one call; the apifacts section in between
    # is ours; localhost is not a host any registry knows (scrub_url drops it).
    assert found("pytest-requests.log") == [
        ("requests", None, "https://api.stripe.com/v1/payment_intents", 400, None)
    ]


def test_httpx_status_error_keeps_no_mdn_link():
    ((source, method, url, status, body),) = found("httpx-raise.log")
    assert (source, method, status, body) == ("httpx", None, 404, None)
    # the spreadsheet id (letters + digits, ≥ 24) is a secret-shaped segment
    assert url == "https://sheets.googleapis.com/v4/spreadsheets/<redacted>/values/Sheet1!A1:B2"


def test_httpx_log_line_with_the_sdk_error_as_body():
    ((source, method, url, status, body),) = found("openai-httpx.log")
    assert (source, method, url, status) == (
        "httpx-log",
        "POST",
        "https://api.openai.com/v1/chat/completions",
        401,
    )
    assert body.startswith("{'error': {'message': 'Incorrect API key provided: <redacted>.")
    assert "sk-proj" not in body and "invalid_api_key" in body


def test_gh_cli_message_is_the_body_and_its_bare_form_is_not_a_call():
    # `gh: Not Found (HTTP 404)` carries no URL: nothing to look up.
    assert found("gh-cli.log") == [
        (
            "gh",
            None,
            "https://api.github.com/repos/octo-org/octo-repo/issues/12/labels",
            403,
            "Resource not accessible by integration",
        )
    ]


def test_axios_config_dump_gives_method_and_url_never_the_request_body():
    ((source, method, url, status, body),) = found("axios.log")
    assert (source, method, url, status) == (
        "axios",
        "POST",
        "https://api.stripe.com/v1/customers",
        401,
    )
    assert body.startswith("{ error: { message: 'Invalid API Key provided")
    assert "jane" not in body and "email" not in body  # config.data is the request body


def test_curl_verbose_command_and_wrapped_command():
    assert found("curl.log") == [
        (
            "curl",
            "GET",
            "https://api.github.com/repos/octo-org/octo-repo/actions/secrets/public-key",
            403,
            '{"message":"Resource not accessible by integration","documentation_url":"<url>",'
            '"status":"403"}',
        ),
        ("curl", "POST", "https://api.telegram.org/<redacted>/sendMessage", 400, None),
        ("curl", "GET", "https://pypi.org/pypi/no-such-package-xyz/json", 404, None),
    ]


def test_stripe_logfmt_method_from_the_request_line():
    ((source, method, url, status, body),) = found("stripe-logfmt.log")
    assert (source, method, url, status) == (
        "stripe-log",
        "POST",
        "https://api.stripe.com/v1/customers/cus_Q1w2E3r4T5y6U7",
        404,
    )
    assert body.startswith("error_code=resource_missing")


def test_ky_and_ofetch_carry_the_method_inline():
    assert found("ky-ofetch.log") == [
        ("ky", "GET", "https://api.github.com/search/repositories", 429, None),
        ("ofetch", "POST", "https://api.telegram.org/<redacted>/sendMessage", 400, None),
    ]


def test_no_secret_from_any_fixture_survives():
    for path in LOGS.glob("*.log"):
        for f in scan(path.read_text()):
            text = f"{f.signal.url} {f.signal.body_excerpt}"
            for secret in ("sk_test_abcdefgh", "sk-proj-", "AAbbccdd", "abcDEF123456789xyz", "?"):
                assert secret not in text, (path.name, text)


def test_own_section_and_annotations_are_not_reported_again():
    log = "\n".join(
        [
            "──── Known facts (apifacts, CC BY 4.0) ────",
            "GET api.github.com/repos/o/r → 404",
            "   note: HTTP 404: Not Found (https://api.github.com/repos/o/r)",  # defensive
            "",
            "::warning title=apifacts%3A GET::HTTP 404: Not Found (https://api.github.com/repos/o/r)",
            "HTTP 410: Gone (https://api.github.com/repos/o/gone)",
        ]
    )
    assert [(f.status, f.url) for f in failures(log)] == [
        (410, "https://api.github.com/repos/o/gone")
    ]


def test_a_call_seen_with_a_method_absorbs_the_same_call_without():
    log = "\n".join(
        [
            'HTTP Request: GET https://api.github.com/repos/o/r "HTTP/1.1 404 Not Found"',
            "httpx.HTTPStatusError: Client error '404 Not Found' for url 'https://api.github.com/repos/o/r'",
            'HTTP Request: DELETE https://api.github.com/repos/o/r "HTTP/1.1 404 Not Found"',
        ]
    )
    assert [(f.signal.method, f.signal.status) for f in scan(log)] == [
        ("GET", 404),
        ("DELETE", 404),
    ]


@pytest.mark.parametrize(
    "line",
    [
        'HTTP Request: GET https://api.github.com/rate_limit "HTTP/1.1 200 OK"',
        'HTTP Request: GET https://api.github.com/rate_limit "HTTP/1.1 304 Not Modified"',
        "curl: (6) Could not resolve host: api.github.com",
        "Request failed with status code 401",  # axios without a config dump below
        "see https://api.github.com/repos/o/r for details: 404",
    ],
)
def test_not_a_failed_call(line):
    assert failures(line) == []


def test_colours_and_runner_timestamps_are_stripped():
    raw = "2026-10-31T09:12:02.1234567Z \x1b[31mE   requests.exceptions.HTTPError\x1b[0m"
    assert clean_lines(raw) == ["E   requests.exceptions.HTTPError"]
