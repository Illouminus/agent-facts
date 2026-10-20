"""`agentfacts check <url-or-locator>`: the plugin's "Known facts" section for humans and agents.

Same request filters as the plugin (query, credentials and secrets never leave), but no host gate:
the user asked explicitly. Exit codes: 0 answered (with or without facts), 1 registry unreachable
or disabled, 2 usage error.
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer

from agentfacts import __version__

EXIT_OK, EXIT_UNREACHABLE, EXIT_USAGE = 0, 1, 2
USER_AGENT = f"agentfacts-cli/{__version__} (+https://github.com/Illouminus/agent-facts)"


def _read_body(path: Path) -> str:
    from agentfacts.client.request import RAW_CHARS

    limit = RAW_CHARS * 4
    if str(path) == "-":
        data = sys.stdin.buffer.read(limit)
    else:
        with path.open("rb") as fh:
            data = fh.read(limit)
    return data.decode("utf-8", "replace")  # an error page in any encoding is still an excerpt


def _fail(message: str, code: int) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(code)


def check(
    target: Annotated[
        str,
        typer.Argument(
            metavar="URL-OR-LOCATOR",
            help="https URL, bare host, or pypi:<package>[@version] / npm:<package>[@version].",
        ),
    ],
    method: Annotated[
        str | None, typer.Option("--method", "-X", help="HTTP method of the failed call.")
    ] = None,
    status: Annotated[
        int | None, typer.Option(min=100, max=599, help="HTTP status you got.")
    ] = None,
    body: Annotated[
        Path | None,
        typer.Option(help="File with the error body ('-' = stdin); redacted, first 2 KB sent."),
    ] = None,
    offline: Annotated[
        bool, typer.Option(help="Answer from the packaged snapshot or AGENTFACTS_SNAPSHOT.")
    ] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Print the raw answer.")] = False,
) -> None:
    """Ask the registry what is known about a call that failed (or is about to be made)."""
    from agentfacts.client.render import render_section, title_line
    from agentfacts.client.request import HTTP_METHODS, make_signal
    from agentfacts.client.settings import Settings
    from agentfacts.client.transport import Client

    if method is not None and method.upper() not in HTTP_METHODS:
        raise _fail(f"unknown method {method!r}", EXIT_USAGE)
    try:
        text = _read_body(body) if body is not None else None
    except OSError as exc:
        raise _fail(f"cannot read --body: {exc}", EXIT_USAGE) from None
    signal = make_signal(target, method=method, status=status, body=text)
    if signal is None:
        raise _fail(f"not an http(s) URL, a host or a pypi:/npm: locator: {target!r}", EXIT_USAGE)

    settings = Settings.from_env()
    if settings.disabled and not offline:
        raise _fail("AGENTFACTS_DISABLE is set; unset it or use --offline", EXIT_UNREACHABLE)
    client = Client(settings.endpoint, USER_AGENT, offline=offline, snapshot=settings.snapshot)
    result = client.check(signal.payload())
    if result is None:
        raise _fail(
            f"registry unreachable at {settings.endpoint}: {client.last_error}", EXIT_UNREACHABLE
        )

    if json_out:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))  # ASCII-escaped: no raw control
        return
    typer.echo(title_line(min(shutil.get_terminal_size((80, 24)).columns, 100)))
    typer.echo(render_section(result, signal, show_empty=True))
