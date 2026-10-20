"""HTTP steps against a local `httpserver`: every request field, auth kinds, refusals (spec 04)."""

import base64
import gzip
import json
import time
import zlib

import httpx
import pytest
from probe_builders import FAKE_KEY, make_service
from werkzeug import Request, Response

from agentfacts.probe import USER_AGENT
from agentfacts.probe.http import (
    MAX_RAW_BYTES,
    Refused,
    _Decoder,
    auth_for,
    base_url_for,
    make_client,
    prepare,
    send,
)
from agentfacts.probe.templating import NOT_JSON, RunContext
from agentfacts.schema.models import HttpStep

SERVICE = make_service()


def step(**fields):
    return HttpStep.model_validate({"do": "http", "method": "GET", "path": "/v1/items", **fields})


def ctx(responses=None, current_step=1):
    c = RunContext.start(current_step=current_step)
    c.responses.update(responses or {})
    return c


class Capture:
    def __init__(self, body=None, status=200, headers=None):
        self.requests: list[Request] = []
        self.forms: list[dict] = []
        self.jsons: list = []
        self.body = body if body is not None else {"ok": True}
        self.status = status
        self.headers = headers or {}

    def __call__(self, request: Request) -> Response:
        self.requests.append(request)
        self.forms.append(dict(request.form))
        self.jsons.append(request.get_json(silent=True))
        return Response(json.dumps(self.body), self.status, self.headers,
                        content_type="application/json")


def run(httpserver, s, *, env="sandbox", key=FAKE_KEY, service=SERVICE, timeout=5.0, c=None):
    request = prepare(s, c or ctx(), service, env)
    headers, query = auth_for(service, key)
    with make_client(timeout=timeout) as client:
        return send(client, httpserver.url_for(""), request, headers, query)


def test_get_with_query_and_json_response(httpserver):
    cap = Capture(body={"data": [1]}, headers={"X-Echo": "hi"})
    httpserver.expect_request("/v1/items", method="GET").respond_with_handler(cap)
    r = run(httpserver, step(query={"limit": 2, "active": True, "q": "a b"}))
    assert r.status == 200 and r.json == {"data": [1]} and r.headers["x-echo"] == "hi"
    assert r.error is None and r.latency_ms >= 0
    args = cap.requests[0].args
    assert (args["limit"], args["active"], args["q"]) == ("2", "true", "a b")


def test_post_form(httpserver):
    cap = Capture()
    httpserver.expect_request("/v1/items", method="POST").respond_with_handler(cap)
    run(httpserver, step(method="POST", form={"amount": 100, "currency": "usd", "live": False}))
    assert cap.forms[0] == {"amount": "100", "currency": "usd", "live": "false"}


def test_post_json_with_templated_values(httpserver):
    cap = Capture()
    httpserver.expect_request("/v1/items", method="POST").respond_with_handler(cap)
    c = ctx({1: {"count": 3, "id": "x"}}, current_step=2)
    body = {"n": "{{step[1].json.count}}", "ref": "r-{{run_uuid}}"}
    run(httpserver, step(method="POST", json=body), c=c)
    assert cap.jsons[0] == {"n": 3, "ref": f"r-{c.run_uuid}"}


def test_probe_headers_are_sent_and_user_agent_is_ours(httpserver):
    cap = Capture()
    httpserver.expect_request("/v1/items").respond_with_handler(cap)
    c = ctx()
    run(httpserver, step(headers={"Idempotency-Key": "{{run_uuid}}", "user-agent": "lie/1.0"}), c=c)
    headers = cap.requests[0].headers
    assert headers["Idempotency-Key"] == c.run_uuid
    assert headers.getlist("User-Agent") == [USER_AGENT]
    assert USER_AGENT.startswith("agent-facts-probe/") and "opt-out: " in USER_AGENT


@pytest.mark.parametrize(
    ("auth", "expect"),
    [
        ({"kind": "bearer", "key_name": "k", "env": "sandbox"}, ("header", "Authorization",
                                                                  f"Bearer {FAKE_KEY}")),
        ({"kind": "basic", "key_name": "k", "env": "sandbox"}, ("header", "Authorization",
         "Basic " + base64.b64encode(f"{FAKE_KEY}:".encode()).decode())),
        ({"kind": "header", "key_name": "k", "env": "sandbox", "header_name": "X-Api-Key"},
         ("header", "X-Api-Key", FAKE_KEY)),
        ({"kind": "query", "key_name": "k", "env": "sandbox", "param_name": "key"},
         ("query", "key", FAKE_KEY)),
    ],
)
def test_auth_kinds_reach_the_server(httpserver, auth, expect):
    cap = Capture()
    httpserver.expect_request("/v1/items").respond_with_handler(cap)
    run(httpserver, step(), service=make_service(auth=auth))
    where, name, value = expect
    seen = cap.requests[0].headers if where == "header" else cap.requests[0].args
    assert seen[name] == value


def test_basic_key_with_colon_is_user_and_password():
    headers, _ = auth_for(make_service(auth={"kind": "basic", "key_name": "k", "env": "sandbox"}),
                          "user:pass")
    assert headers["Authorization"] == "Basic " + base64.b64encode(b"user:pass").decode()


def test_auth_none_step_sends_no_credential(httpserver):
    cap = Capture()
    httpserver.expect_request("/v1/items").respond_with_handler(cap)
    s = step(auth="none")
    request = prepare(s, ctx(), SERVICE, "sandbox")
    assert not request.uses_key
    with make_client() as client:
        send(client, httpserver.url_for(""), request, {}, {})
    assert "Authorization" not in cap.requests[0].headers


def test_keyless_service_has_no_auth():
    assert auth_for(make_service(auth={"kind": "none"}), None) == ({}, {})
    assert auth_for(make_service(), None) == ({}, {})


def test_redirect_is_not_followed(httpserver):
    httpserver.expect_request("/v1/redirect").respond_with_response(
        Response("", 302, {"Location": httpserver.url_for("/v1/items")})
    )
    r = run(httpserver, step(path="/v1/redirect"))
    assert r.status == 302
    assert all(req.path != "/v1/items" for req, _ in httpserver.log)


def test_timeout_is_a_normalized_error(httpserver):
    def slow(request):
        time.sleep(0.5)
        return Response("{}", 200)

    httpserver.expect_request("/v1/slow").respond_with_handler(slow)
    r = run(httpserver, step(path="/v1/slow"), timeout=0.1)
    assert r.status is None and r.error == "timeout" and r.json is NOT_JSON


def test_connect_error_is_normalized():
    request = prepare(step(), ctx(), SERVICE, "sandbox")
    with make_client(timeout=1.0) as client:
        r = send(client, "http://127.0.0.1:9", request, {}, {})
    assert r.status is None and r.error == "connect_error"


def test_body_is_capped(httpserver):
    httpserver.expect_request("/v1/big").respond_with_data(b"x" * (3 * 1024 * 1024))
    r = run(httpserver, step(path="/v1/big"))
    assert r.status == 200 and len(r.body) == 1024 * 1024 and r.json is NOT_JSON


def test_gzip_body_is_decoded_but_capped_and_identity_is_asked(httpserver):
    bomb = gzip.compress(b"0" * (8 * 1024 * 1024))
    cap = Capture()

    def handler(request):
        cap.requests.append(request)
        return Response(bomb, 200, {"Content-Encoding": "gzip"})

    httpserver.expect_request("/v1/big").respond_with_handler(handler)
    r = run(httpserver, step(path="/v1/big"))
    assert r.status == 200 and len(r.body) == 1024 * 1024 and set(r.body) == {ord("0")}
    assert cap.requests[0].headers["Accept-Encoding"] == "identity"


def test_gzip_and_deflate_json_bodies_are_parsed(httpserver):
    payload = json.dumps({"ok": 1}).encode()
    httpserver.expect_request("/v1/items").respond_with_response(
        Response(gzip.compress(payload), 200, {"Content-Encoding": "gzip"}))
    httpserver.expect_request("/v1/big").respond_with_response(
        Response(zlib.compress(payload), 200, {"Content-Encoding": "deflate"}))
    assert run(httpserver, step()).json == {"ok": 1}
    assert run(httpserver, step(path="/v1/big")).json == {"ok": 1}


def test_decoder_stops_at_end_of_stream_and_on_corrupt_data():
    d = _Decoder("gzip")
    assert d.feed(gzip.compress(b"abc"), 100) == b"abc" and d.done
    bad = _Decoder("gzip")
    assert bad.feed(b"not gzip at all", 100) == b"" and bad.done
    raw = _Decoder("deflate")
    deflater = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    assert raw.feed(deflater.compress(b"xyz") + deflater.flush(), 100) == b"xyz"
    plain = _Decoder(None)
    assert plain.feed(b"abcdef", 3) == b"abc" and not plain.done


def test_trailing_garbage_after_gzip_is_not_read(httpserver):
    junk = gzip.compress(json.dumps({"ok": 1}).encode()) + b"\x00" * (2 * MAX_RAW_BYTES)
    httpserver.expect_request("/v1/items").respond_with_response(
        Response(junk, 200, {"Content-Encoding": "gzip"}))
    assert run(httpserver, step()).json == {"ok": 1}


def test_unknown_encoding_is_kept_raw(httpserver):
    httpserver.expect_request("/v1/items").respond_with_response(
        Response(b"\x00\x01raw", 200, {"Content-Encoding": "br"}))
    r = run(httpserver, step())
    assert r.body == b"\x00\x01raw" and r.json is NOT_JSON


def test_slow_drip_body_hits_the_total_deadline(httpserver):
    def drip(request):
        def chunks():
            for _ in range(40):
                time.sleep(0.05)
                yield b"x" * 10
        return Response(chunks(), 200)

    httpserver.expect_request("/v1/slow").respond_with_handler(drip)
    started = time.perf_counter()
    r = run(httpserver, step(path="/v1/slow"), timeout=0.3)
    assert r.error == "timeout" and r.status is None
    assert time.perf_counter() - started < 1.5


def test_non_json_body(httpserver):
    httpserver.expect_request("/v1/items").respond_with_data("<html>no</html>", status=500)
    r = run(httpserver, step())
    assert r.status == 500 and r.json is NOT_JSON and b"html" in r.body


def test_rendered_path_must_match_a_template():
    c = ctx({1: {"id": "a/b"}}, current_step=2)
    with pytest.raises(Refused) as exc:
        prepare(step(path="/v1/items/{{step[1].json.id}}"), c, SERVICE, "sandbox")
    assert exc.value.code == "unregistered_template"
    with pytest.raises(Refused) as exc:
        prepare(step(path="/v1/other"), ctx(), SERVICE, "sandbox")
    assert exc.value.code == "unregistered_template"


def test_templated_path_instance_is_accepted():
    c = ctx({1: {"id": "it_1"}}, current_step=2)
    request = prepare(step(path="/v1/items/{{step[1].json.id}}"), c, SERVICE, "sandbox")
    assert (request.path, request.template) == ("/v1/items/it_1", "/v1/items/{id}")


def test_prod_post_is_refused_before_any_request(httpserver):
    prod = make_service(auth={"kind": "bearer", "key_name": "acme-live", "env": "prod"})
    with pytest.raises(Refused) as exc:
        prepare(step(method="POST", form={"a": 1}), ctx(), prod, "prod")
    assert exc.value.code == "prod_probe_not_readonly"
    assert httpserver.log == []


def test_prod_method_override_header_is_refused():
    prod = make_service(auth={"kind": "none"})
    with pytest.raises(Refused) as exc:
        prepare(step(headers={"X-HTTP-Method-Override": "DELETE"}), ctx(), prod, "prod")
    assert exc.value.code == "prod_probe_not_readonly"


def test_keyed_step_in_another_env_than_the_key_is_refused():
    with pytest.raises(Refused) as exc:
        prepare(step(), ctx(), SERVICE, "prod")  # the acme key reaches sandbox
    assert exc.value.code == "auth_env_mismatch"
    assert not prepare(step(auth="none"), ctx(), SERVICE, "prod").uses_key


@pytest.mark.parametrize("value", ["caf\u00e9", "{{step[1].json.name}}", "a\r\nX-Evil: 1"])
def test_header_values_must_be_ascii_without_line_breaks(value):
    c = ctx({1: {"name": "\u65e5\u672c"}}, current_step=2)
    with pytest.raises(Refused) as exc:
        prepare(step(headers={"X-Ref": value}), c, SERVICE, "sandbox")
    assert exc.value.code == "invalid_header"


def test_raw_deflate_whose_first_byte_looks_like_zlib():
    import struct

    # Stored, non-final block starting with byte 0x08 (low nibble 8) but no valid zlib header.
    stream = b"\x08" + struct.pack("<HH", 3, 0xFFFF ^ 3) + b"abc" + b"\x01\x00\x00\xff\xff"
    assert (0x08 << 8 | stream[1]) % 31 != 0
    assert _Decoder("deflate").feed(stream, 100) == b"abc"


def test_template_error_is_refused():
    with pytest.raises(Refused) as exc:
        prepare(step(headers={"X-Ref": "{{nope}}"}), ctx(), SERVICE, "sandbox")
    assert exc.value.code == "template_error"


def test_base_url_is_the_env_url_on_a_vendor_host():
    assert base_url_for(SERVICE, "sandbox") == "https://api.acme.example"
    foreign = make_service(dimensions={"env": {"sandbox": "https://evil.example.org"}})
    with pytest.raises(Refused) as exc:
        base_url_for(foreign, "sandbox")
    assert exc.value.code == "foreign_host"
    with pytest.raises(Refused) as exc:
        base_url_for(make_service(dimensions={"env": {"sandbox": "https://api.acme.example"}}),
                     "prod")
    assert exc.value.code == "env_not_offered"


def test_client_ignores_environment_proxies_and_netrc():
    with make_client() as client:
        assert isinstance(client, httpx.Client)
        assert client.trust_env is False
        assert client.follow_redirects is False
