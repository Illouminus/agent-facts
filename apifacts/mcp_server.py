"""`apifacts mcp`: an MCP server over stdio with one tool, `check` (spec 07, wave 2).

No resources and no prompts. The tool goes through the same client as the CLI and the plugin
(`apifacts.client`: the same request filters, 2 s timeout, at most 20 checks per session) and
answers with the same "Known facts" text. A failure is an answer too: the tool returns a line
saying why, never an exception. Needs the `mcp` extra: `uvx --from 'apifacts[mcp]' apifacts mcp`.
"""

import json
from typing import Annotated, Any

from pydantic import Field

from apifacts import __version__

USER_AGENT = f"apifacts-mcp/{__version__} (+https://github.com/Illouminus/apifacts)"
NAME = "apifacts"
TOOL_DESCRIPTION = (
    "Verified facts about a failing third-party API call: send the URL, HTTP method, status and "
    "response body; get known causes and typed fixes (Stripe, GitHub, Google, Telegram, "
    "Salesforce, PyPI, Solana). Sends the response body only, never request headers or keys."
)
INSTRUCTIONS = (
    "Call `check` when a request to a third-party API returned HTTP status >= 400, before guessing "
    "a fix. Pass the response body only."
)


def answer(
    target: str,
    method: str | None = None,
    status: int | None = None,
    body: str | None = None,
    *,
    client: Any,
    disabled: bool = False,
) -> str:
    """The tool's text for one call; `client` is the session's `Client` (tests pass their own)."""
    from apifacts.client.render import TITLE, render_section
    from apifacts.client.request import HTTP_METHODS, make_signal

    if method is not None and method.upper() not in HTTP_METHODS:
        return f"error: unknown method {method!r}"
    signal = make_signal(target, method=method, status=status, body=body)
    if signal is None:
        return f"error: not an http(s) URL, a host or a pypi:/npm: locator: {target!r}"
    if not signal.complete:
        return "error: a URL with a path needs `method`"
    if disabled:
        return "error: APIFACTS_DISABLE is set; the registry is not called"
    result = client.check(signal.payload())
    if result is None:
        return f"error: registry did not answer at {client.endpoint}: {client.last_error}"
    return f"{TITLE}\n{render_section(result, signal, show_empty=True)}"


def build_server(offline: bool = False) -> Any:
    """The MCP server object (`mcp.server.MCPServer`), not started; settings from the environment
    (`APIFACTS_ENDPOINT`, `APIFACTS_SNAPSHOT`, `APIFACTS_DISABLE`), read once per session."""
    from mcp.server import MCPServer

    from apifacts.client.settings import Settings
    from apifacts.client.transport import Client

    settings = Settings.from_env()
    session = Client(settings.endpoint, USER_AGENT, offline=offline, snapshot=settings.snapshot)
    disabled = settings.disabled and not offline
    server = MCPServer(NAME, version=__version__, instructions=INSTRUCTIONS)

    @server.tool(name="check", description=TOOL_DESCRIPTION, structured_output=False)
    def check(
        target: Annotated[
            str, Field(description="URL that failed, e.g. https://api.stripe.com/v1/customers")
        ],
        method: Annotated[
            str | None, Field(description="HTTP method; required for a URL with a path")
        ] = None,
        status: Annotated[
            int | None, Field(description="HTTP status you got", ge=100, le=599)
        ] = None,
        body: Annotated[
            str | dict[str, Any] | list[Any] | None,
            Field(description="Response body (first 2 KB sent, redacted)"),
        ] = None,
    ) -> str:
        if body is not None and not isinstance(body, str):  # the SDK parses a JSON string itself
            body = json.dumps(body, ensure_ascii=False)
        return answer(target, method, status, body, client=session, disabled=disabled)

    return server


def run(offline: bool = False) -> None:
    build_server(offline).run("stdio")
