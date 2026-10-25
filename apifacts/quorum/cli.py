"""`apifacts quorum run`: observations of the salt period → fact drafts (spec 05)."""

import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Observation quorum: reported fact drafts.", no_args_is_help=True)

EXIT_OK, EXIT_PROBLEMS, EXIT_USAGE = 0, 1, 2


def _date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter("expected a date YYYY-MM-DD") from None


@app.command()
def run(
    root: Annotated[
        Path, typer.Option(help="Repository root (services/, facts/, probes/).")
    ] = Path("."),
    db: Annotated[
        Path | None,
        typer.Option(help="observations.sqlite; default: $APIFACTS_DB or ./observations.sqlite."),
    ] = None,
    state_dir: Annotated[
        Path | None, typer.Option(help="Probe runner state; default: <root>/var.")
    ] = None,
    vantage: Annotated[str, typer.Option(help="Runner whose probes get requested.")] = "illouminus",
    since_period: Annotated[
        str | None,
        typer.Option(
            "--since-period",
            callback=_date,
            help="YYYY-MM-DD: evaluate the salt period (Monday → Sunday UTC) holding this date; "
            "default: the current one.",
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print what would happen; write nothing.")
    ] = False,
) -> None:
    """One quorum pass: draft new `reported` facts, refresh known ones, request their probes.

    Exit codes: 0 done (also when killed or nothing met quorum), 1 a draft failed validation,
    2 usage.
    """
    from apifacts.quorum.run import run_quorum

    db = db or Path(os.environ.get("APIFACTS_DB", "observations.sqlite"))
    now = datetime.now(UTC)
    if since_period is not None and since_period > now.date():
        raise typer.BadParameter("--since-period is in the future")
    try:
        report = run_quorum(
            root, db, state_dir or root / "var", now=now, vantage=vantage, since=since_period,
            dry_run=dry_run, environ=os.environ,
        )
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    start, end = report.window
    span = f"{start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M} UTC"
    if report.killed:
        typer.echo(f"killed ({report.killed}): nothing done", err=True)
        raise typer.Exit(EXIT_OK)
    for line in report.lines:
        if line.action == "below":
            continue
        where = line.path.relative_to(root).as_posix() if line.path else "-"
        typer.echo(f"{line.action:8} {line.fact_id or '-'}  {where}  [{line.group.label}] "
                   f"{line.detail}".rstrip())
    for problem in report.problems:
        typer.echo(str(problem))
    counts = ", ".join(
        f"{report.count(a)} {a}" for a in ("draft", "refresh", "covered", "below", "skipped")
    )
    prefix = "dry run: " if dry_run else ""
    typer.echo(f"{prefix}{len(report.lines)} groups in {span}: {counts}", err=True)
    raise typer.Exit(EXIT_OK if report.ok else EXIT_PROBLEMS)
