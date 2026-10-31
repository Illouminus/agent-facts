"""Command-line entry point: `apifacts <command>`."""

import json
from pathlib import Path
from typing import Annotated

import typer

from apifacts import __version__, cli_check, cli_scan
from apifacts.bot.cli import app as bot_app
from apifacts.pages.cli import app as pages_app
from apifacts.probe.cli import app as probe_app
from apifacts.quorum.cli import app as quorum_app

app = typer.Typer(
    help="apifacts: verified facts about machine interfaces for AI agents.",
    no_args_is_help=True,
    add_completion=False,
)

EXIT_OK, EXIT_INVALID, EXIT_USAGE = 0, 1, 2

app.add_typer(pages_app, name="pages")
app.command("check")(cli_check.check)
app.command("scan")(cli_scan.scan)
app.add_typer(probe_app, name="probe")
app.add_typer(quorum_app, name="quorum")
app.add_typer(bot_app, name="bot")


@app.callback()
def main() -> None:
    """Root callback: keeps every command a subcommand."""


@app.command()
def version() -> None:
    """Print the apifacts version."""
    typer.echo(__version__)


@app.command()
def mcp(
    offline: Annotated[
        bool, typer.Option(help="Answer from the packaged snapshot or APIFACTS_SNAPSHOT.")
    ] = False,
) -> None:
    """Run the MCP server on stdio: one tool, `check` (needs the extra: apifacts[mcp])."""
    try:
        import mcp.server  # noqa: F401
    except ImportError:
        typer.echo(
            "error: the MCP server needs the extra: uvx --from 'apifacts[mcp]' apifacts mcp",
            err=True,
        )
        raise typer.Exit(EXIT_USAGE) from None
    from apifacts.mcp_server import run

    run(offline)


@app.command()
def validate(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help="Files or directories; default: services/ facts/ probes/ under --root."
        ),
    ] = None,
    root: Annotated[
        Path, typer.Option(help="Repository root; its services/ and probes/ are loaded as context.")
    ] = Path("."),
) -> None:
    """Validate registry YAML: one `file:line: code message` per problem.

    Exit codes: 0 valid, 1 invalid, 2 usage error.
    """
    from apifacts.schema.validate import default_paths, validate_paths

    try:
        report = validate_paths(paths or default_paths(root), root=root)
    except FileNotFoundError as exc:
        typer.echo(f"error: no such path: {exc.args[0]}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    for problem in report.problems:
        typer.echo(str(problem))
    if report.ok:
        kinds = ", ".join(f"{n} {kind}" for kind, n in sorted(report.counts.items()))
        typer.echo(f"ok: {report.files} files" + (f" ({kinds})" if kinds else ""), err=True)
        raise typer.Exit(EXIT_OK)
    bad_files = len({p.file for p in report.problems})
    typer.echo(
        f"invalid: {len(report.problems)} problems in {bad_files} of {report.files} files", err=True
    )
    raise typer.Exit(EXIT_INVALID)


stats_app = typer.Typer(
    help="Numbers read from the API's var/ (sqlite, reader counts).", no_args_is_help=True
)
app.add_typer(stats_app, name="stats")


@stats_app.command("adoption")
def stats_adoption(
    db: Annotated[Path, typer.Option(help="The API's sqlite file.")] = Path(
        "var/observations.sqlite"
    ),
    current: Annotated[
        bool, typer.Option(help="The running salt period instead of the last complete one.")
    ] = False,
    now: Annotated[
        str | None, typer.Option(help="ISO time with offset (default: now); for tests.")
    ] = None,
) -> None:
    """One line for the gate (D-092): external_clients=N calls=M reported_external=K.

    Window = one salt period (Monday 00:00 UTC → Monday), the only one where distinct networks
    are exact. Exit codes: 0 printed, 1 no db or no traffic table yet, 2 usage.
    """
    from datetime import UTC, datetime

    from apifacts.api.adoption import period_of, read_adoption

    try:
        moment = datetime.fromisoformat(now) if now else datetime.now(UTC)
    except ValueError:
        typer.echo(f"error: --now needs an ISO time, got {now!r}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    if moment.tzinfo is None:
        typer.echo("error: --now needs an offset", err=True)
        raise typer.Exit(EXIT_USAGE)
    found = read_adoption(db, period_of(moment.astimezone(UTC), current))
    typer.echo(found.line())
    if not found.available:
        typer.echo(f"error: {db}: no traffic table (API older than D-092 counting)", err=True)
        raise typer.Exit(EXIT_INVALID)


@stats_app.command("readers")
def stats_readers(
    days: Annotated[int, typer.Option(min=1, max=400, help="UTC days back, today included.")] = 7,
    readers_dir: Annotated[
        Path, typer.Option("--dir", help="The API's reader counts (APIFACTS_READERS_DIR).")
    ] = Path("var/readers"),
    now: Annotated[
        str | None, typer.Option(help="ISO time with offset (default: now); for tests.")
    ] = None,
) -> None:
    """Who reads apifacts.dev: requests by User-Agent family, path class and status class.

    Counts only (apifacts/api/readers.py): no path, no raw User-Agent, no IP. Today is partial
    (the API flushes every 5 minutes). Exit codes: 0 printed, 1 no directory yet, 2 usage.
    """
    from datetime import UTC, datetime, timedelta

    from apifacts.api.readers import GROUPS, STATUS_CLASSES, group_of, read_readers

    try:
        moment = datetime.fromisoformat(now) if now else datetime.now(UTC)
    except ValueError:
        typer.echo(f"error: --now needs an ISO time, got {now!r}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    if moment.tzinfo is None:
        typer.echo("error: --now needs an offset", err=True)
        raise typer.Exit(EXIT_USAGE)
    today = moment.astimezone(UTC).date()
    span = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    found = read_readers(readers_dir, span)
    if not found.available:
        typer.echo(f"error: {readers_dir}: no such directory (API without reader counts yet)",
                   err=True)
        raise typer.Exit(EXIT_INVALID)
    bad = f", {found.bad_files} unreadable" if found.bad_files else ""
    typer.echo(f"readers {span[0]}..{span[-1]} UTC ({found.days_found}/{days} days with data{bad},"
               f" today partial): {found.total} requests")
    if not found.total:
        return
    typer.echo(f"{'group':<11} {'family':<20} {'total':>6} "
               + " ".join(f"{s:>5}" for s in STATUS_CLASSES) + "  paths")
    families = found.by_family()
    order = sorted(families, key=lambda f: (GROUPS.index(group_of(f)), -families[f], f))
    for family in order:
        statuses = found.statuses(family)
        paths = sorted(found.paths_of(family).items(), key=lambda pn: (-pn[1], pn[0]))
        typer.echo(f"{group_of(family):<11} {family:<20} {families[family]:>6} "
                   + " ".join(f"{statuses.get(s, 0):>5}" for s in STATUS_CLASSES)
                   + "  " + ", ".join(f"{p} {n}" for p, n in paths))


@app.command("render-fix")
def render_fix(
    fix_json: Annotated[str, typer.Argument(metavar="JSON", help="One fix as a JSON object.")],
) -> None:
    """Render one typed fix as its English sentence (exit 1 if the fix is invalid)."""
    from apifacts.fixes.templates import render_fix as render
    from apifacts.schema.validate import fix_problems

    try:
        fix = json.loads(fix_json)
    except json.JSONDecodeError as exc:
        typer.echo(f"error: not valid JSON: {exc}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    problems = fix_problems(fix)
    if problems:
        for problem in problems:
            typer.echo(str(problem))
        raise typer.Exit(EXIT_INVALID)
    typer.echo(render(fix))

