import types

import httpx
import pytest
import requests

from agentfacts_pytest.extract import iter_chain, sdk_context, signal_from_exception

URL = "https://api.stripe.com/v1/payment_intents?expand[]=customer"
CLEAN = "https://api.stripe.com/v1/payment_intents"
BODY = b'{"error": {"code": "idempotency_error", "message": "Keys for idempotent requests"}}'


def requests_error(status=400, content=BODY, method="POST"):
    response = requests.Response()
    response.status_code = status
    response._content = content
    response.url = URL
    response.request = requests.Request(
        method, URL, data={"card": "4242"}, headers={"Authorization": "Bearer sk_live_x1y2z3w4"}
    ).prepare()
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        return exc
    raise AssertionError("raise_for_status did not raise")


def httpx_error(status=400, **kw):
    request = httpx.Request("POST", URL, headers={"Authorization": "Bearer sk_live_x1y2z3w4"})
    response = httpx.Response(status, request=request, **kw)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return exc
    raise AssertionError("raise_for_status did not raise")


def test_requests_http_error():
    signal = signal_from_exception(requests_error())
    assert (signal.method, signal.url, signal.status) == ("POST", CLEAN, 400)
    assert signal.body_excerpt == BODY.decode()
    assert signal.sdk is None  # requests is the HTTP library, not a vendor SDK


def test_httpx_status_error():
    signal = signal_from_exception(httpx_error(content=BODY))
    assert (signal.method, signal.url, signal.status) == ("POST", CLEAN, 400)
    assert signal.body_excerpt == BODY.decode()


class APIStatusError(Exception):
    """Shaped like openai/anthropic: status_code, request (httpx), response."""

    def __init__(self, message, *, response):
        super().__init__(message)
        self.response = response
        self.request = response.request
        self.status_code = response.status_code


def test_sdk_error_with_status_code_and_request_url():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(429, request=request, json={"error": {"type": "rate_limit"}})
    signal = signal_from_exception(APIStatusError("Error code: 429", response=response))
    assert (signal.method, signal.url, signal.status) == (
        "POST",
        "https://api.openai.com/v1/responses",
        429,
    )
    assert "rate_limit" in signal.body_excerpt


def test_object_with_http_status_and_request_url():
    exc = Exception("Request req_1: no such customer")
    exc.http_status = 404
    exc.request = types.SimpleNamespace(
        url="https://api.stripe.com/v1/customers/cus_1", method="get"
    )
    signal = signal_from_exception(exc)
    assert (signal.method, signal.url, signal.status) == (
        "GET",
        "https://api.stripe.com/v1/customers/cus_1",
        404,
    )
    assert signal.body_excerpt == "Request req_1: no such customer"  # str(exc) when no body


def test_aiohttp_shaped_error():
    exc = Exception("401, message='Unauthorized'")
    exc.status = 401
    exc.request_info = types.SimpleNamespace(url="https://api.github.com/user", method="GET")
    signal = signal_from_exception(exc)
    assert (signal.method, signal.url, signal.status) == ("GET", "https://api.github.com/user", 401)


def test_explicit_cause_is_followed():
    http = requests_error()
    try:
        raise RuntimeError("payment failed") from http
    except RuntimeError as exc:
        wrapped = exc
    assert signal_from_exception(wrapped).status == 400


def test_implicit_context_is_followed():
    try:
        try:
            raise httpx_error(status=503)
        except httpx.HTTPStatusError:
            raise ValueError("retry exhausted") from None
    except ValueError as exc:
        wrapped = exc
    assert wrapped.__suppress_context__ and signal_from_exception(wrapped).status == 503


def test_exception_group_is_searched():
    group = ExceptionGroup("tasks", [ValueError("x"), httpx_error(status=502)])
    assert signal_from_exception(group).status == 502


def test_cycles_terminate():
    a, b = ValueError("a"), ValueError("b")
    a.__context__, b.__context__ = b, a
    assert list(iter_chain(a)) == [a, b]
    assert signal_from_exception(a) is None


def test_outermost_http_error_wins():
    inner = httpx_error(status=500)
    outer = requests_error(status=404)
    outer.__cause__ = inner
    assert signal_from_exception(outer).status == 404


@pytest.mark.parametrize("status", [True, 42, 700, "400", None])
def test_bad_status_gives_no_signal(status):
    exc = Exception("x")
    exc.status_code = status
    exc.request = types.SimpleNamespace(url="https://api.stripe.com/v1/x", method="GET")
    assert signal_from_exception(exc) is None


def test_no_url_gives_no_signal():
    exc = Exception("x")
    exc.status_code = 400
    assert signal_from_exception(exc) is None


def test_raising_attributes_never_escape():
    class Hostile(Exception):
        @property
        def response(self):
            raise RuntimeError("boom")

        @property
        def status_code(self):
            raise RuntimeError("boom")

        def __str__(self):
            raise RuntimeError("boom")

    assert signal_from_exception(Hostile()) is None


def test_unread_httpx_stream_is_not_read():
    request = httpx.Request("GET", "https://api.github.com/user")
    response = httpx.Response(401, request=request, stream=httpx.ByteStream(b"never read"))
    exc = httpx.HTTPStatusError(
        "Client error '401 Unauthorized'", request=request, response=response
    )
    signal = signal_from_exception(exc)
    assert signal.status == 401
    assert signal.body_excerpt == "Client error '401 Unauthorized'"
    assert not response.is_closed and not hasattr(response, "_content")


def test_unread_requests_stream_is_not_read():
    response = requests.Response()
    response.status_code = 500
    response.url = "https://api.github.com/repos"
    response.request = requests.Request("GET", response.url).prepare()

    class Raw:
        def read(self, *a, **kw):
            raise AssertionError("the plugin read a streaming body")

        def stream(self, *a, **kw):
            raise AssertionError("the plugin read a streaming body")

    response.raw = Raw()  # _content stays False: not consumed
    exc = requests.HTTPError("500 Server Error", response=response)
    signal = signal_from_exception(exc)
    assert signal.status == 500 and signal.body_excerpt == "500 Server Error"


def test_body_secrets_are_redacted():
    body = b'{"error": {"message": "Invalid API Key provided: sk_test_abcdefgh12345678"}}'
    signal = signal_from_exception(requests_error(status=401, content=body))
    assert "sk_test_abcdefgh12345678" not in signal.body_excerpt
    assert "<redacted>" in signal.body_excerpt


def test_sdk_context_for_a_vendor_package():
    vendor = type("BadRequestError", (Exception,), {"__module__": "pytest_httpserver.errors"})
    import importlib.metadata as md

    assert sdk_context(vendor("x")) == {
        "package": "pytest-httpserver",
        "ecosystem": "pypi",
        "version": md.version("pytest-httpserver"),
    }


@pytest.mark.parametrize(
    "exc",
    [requests_error(), httpx_error(), ValueError("x"), APIStatusError.__new__(APIStatusError)],
)
def test_no_sdk_context_for_http_libraries_or_local_code(exc):
    assert sdk_context(exc) is None
