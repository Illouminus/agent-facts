"""Command-line entry point: `apifacts <command>`."""

import json
from pathlib import Path
from typing import Annotated

import typer

from apifacts import __version__, cli_check
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

