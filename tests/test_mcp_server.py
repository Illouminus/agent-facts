"""`apifacts mcp` (spec 07, wave 2): one tool `check`, same client and text as the CLI."""

import json
import sys
from pathlib import Path

import anyio
import pytest
from mcp.client.client import Client
from mcp.client.stdio import StdioServerParameters

from apifacts.api.match import classify_ua
from apifacts.client.render import TITLE
from apifacts.mcp_server import TOOL_DESCRIPTION, build_server
from apifacts.schema.yamlio import load_yaml, plain

VALID = Path(__file__).parent / "fixtures" / "valid"
URL = "https://api.stripe.com/v1/payment_intents?expand[]=customer"
SECRET = "sk_test_abcdefgh12345678"


def answer():
    fact = plain(load_yaml(VALID / "fact-idempotency-key-reuse-different-params.yaml"))
    return {
        "service": "stripe",
        "matched_template": {"method": "POST", "path": "/v1/payment_intents"},
        "facts": [fact],
        "registry": {"version": "2026-10-20", "license": "CC-BY-4.0"},
    }


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    for name in ("APIFACTS_DISABLE", "APIFACTS_SNAPSHOT", "APIFACTS_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture
def server(httpserver, env):
    env.setenv("APIFACTS_ENDPOINT", httpserver.url_for("").rstrip("/"))
    return httpserver


def call(target, **arguments):
    async def go():
        async with Client(build_server(arguments.pop("offline", False))) as client:
            result = await client.call_tool("check", {"target": target, **arguments})
            return result.content[0].text

    return anyio.run(go)


def await_(request):
    async def go():
        async with Client(build_server()) as client:
            return await request(client)

    return anyio.run(go)


def test_one_tool_no_resources_no_prompts(env):
    async def go():
        async with Client(build_server()) as client:
            tools = (await client.list_tools()).tools
            return tools

    tools = anyio.run(go)
    assert [t.name for t in tools] == ["check"]
    assert tools[0].description == TOOL_DESCRIPTION
    assert len(TOOL_DESCRIPTION.split()) <= 40
    assert set(tools[0].input_schema["properties"]) == {"target", "method", "status", "body"}
    assert tools[0].input_schema["required"] == ["target"]
    assert not (await_(lambda c: c.list_resources())).resources
    assert not (await_(lambda c: c.list_prompts())).prompts


def test_check_answers_with_the_known_facts(server):
    server.expect_request("/v0/check", method="POST").respond_with_json(answer())
    text = call(URL, method="post", status=400, body=f'{{"message": "key {SECRET}"}}')
    lines = text.splitlines()
    assert lines[0] == TITLE
    assert lines[1] == "POST api.stripe.com/v1/payment_intents → 400 idempotency_error"
    assert lines[2].startswith("✅ verified:server:prod · Reusing an Idempotency-Key")
    (request,) = [r for r, _ in server.log if r.path == "/v0/check"]
    sent = json.loads(request.get_data())
    assert sent["target"] == {"method": "POST", "url": "https://api.stripe.com/v1/payment_intents"}
    assert sent["error"]["status"] == 400 and SECRET not in request.get_data(as_text=True)
    assert request.headers["User-Agent"].startswith("apifacts-mcp/")
    assert classify_ua(request.headers["User-Agent"]) == "mcp"  # the class the API stores


def test_body_as_a_json_string_or_object(server):
    server.expect_request("/v0/check", method="POST").respond_with_json(answer())
    for body in ('{"error": {"message": "x"}}', {"error": {"message": "x"}}):
        text = call(f"{URL}&n={len(str(body))}", method="POST", status=400, body=body)
        assert text.splitlines()[0] == TITLE, text
    sent = [json.loads(r.get_data()) for r, _ in server.log if r.path == "/v0/check"]
    assert [s["error"]["body_excerpt"] for s in sent] == ['{"error": {"message": "x"}}'] * 2


def test_network_failure_is_a_text_answer(env):
    env.setenv("APIFACTS_ENDPOINT", "http://127.0.0.1:9")  # nothing listens on discard
    text = call(URL, method="POST", status=400)
    assert text.startswith("error: registry did not answer at http://127.0.0.1:9")


def test_bad_input_is_a_text_answer(env):
    assert call(URL, status=400) == "error: a URL with a path needs `method`"
    assert call("ftp://x", method="GET").startswith("error: not an http(s) URL")
    assert call(URL, method="FETCH").startswith("error: unknown method")


def test_disable_holds(server, env):
    env.setenv("APIFACTS_DISABLE", "1")
    assert call(URL, method="POST", status=400).startswith("error: APIFACTS_DISABLE is set")
    assert not [r for r, _ in server.log if r.path == "/v0/check"]


def test_offline_answers_from_the_snapshot(env):
    text = call("https://api.stripe.com/v1/customers", method="GET", status=401, offline=True)
    assert text.splitlines()[0] == TITLE
    assert "api.stripe.com/v1/customers → 401" in text.splitlines()[1]


def test_stdio_subcommand_serves_the_tool(env):
    """`apifacts mcp` as a process: what `uvx --from 'apifacts[mcp]' apifacts mcp` starts."""
    params = StdioServerParameters(
        command=str(Path(sys.executable).parent / "apifacts"), args=["mcp", "--offline"]
    )

    async def go():
        async with Client(params) as client:
            return [t.name for t in (await client.list_tools()).tools]

    assert anyio.run(go) == ["check"]


def test_server_json_matches_the_package():
    """The registry entry: same name as README's mcp-name line (the registry checks it on PyPI),
    same version as the package, launched as `uvx --from 'apifacts[mcp]==V' apifacts mcp`."""
    from apifacts import __version__

    root = Path(__file__).parent.parent
    entry = json.loads((root / "server.json").read_text(encoding="utf-8"))
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert f"<!-- mcp-name: {entry['name']} -->" in readme
    assert len(entry["description"]) <= 100  # registry schema maxLength
    (package,) = entry["packages"]
    assert entry["version"] == package["version"] == __version__
    assert package["identifier"] == "apifacts" and package["transport"] == {"type": "stdio"}
    assert package["runtimeArguments"] == [
        {"type": "named", "name": "--from", "value": f"apifacts[mcp]=={__version__}"}
    ]
    assert package["packageArguments"] == [{"type": "positional", "value": "mcp"}]
