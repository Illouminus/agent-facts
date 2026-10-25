"""`apifacts bot publish`: changed fact files → one PR (spec 05 Bot)."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="The facts bot: publish changed fact files as one PR.",
                  no_args_is_help=True)

EXIT_OK, EXIT_REFUSED, EXIT_USAGE = 0, 1, 2


@app.command()
def publish(
    root: Annotated[Path, typer.Option(help="The runner's checkout of the repository.")] = Path(
        "."
    ),
    vantage: Annotated[
        str, typer.Option(help="Runner named in the commit trailer.")
    ] = "illouminus",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the PR that would open; push and call nothing.")
    ] = False,
    state_dir: Annotated[
        Path | None,
        typer.Option(help="Runner state (evidence-refresh.json, bot-state.json); <root>/var."),
    ] = None,
) -> None:
    """Commit changed facts/ (and regenerated pages/) on bot/facts-<date>-<n>, open one PR
    labelled `facts`; auto-merge only when every fact is `verified:*` and written by the bot,
    otherwise the label `needs-review` (D-089). New facts and status changes go out at once;
    counter-only changes once a day, after `probe run --refresh-evidence`. GitHub access only
    with the bot's own token (`keyput agent-facts-bot`).

    Exit codes: 0 done / nothing to do / waiting / killed, 1 refused (invalid or conflicting
    files, git or gh failure), 2 usage.
    """
    from apifacts.bot.collect import GitError
    from apifacts.bot.pr import publish as run

    try:
        report = run(root, today=datetime.now(UTC).date(), vantage=vantage, dry_run=dry_run,
                     environ=os.environ, state_dir=state_dir)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    except GitError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_REFUSED) from None
    for row in report.rows:
        flag = "auto" if row.eligible else "review"
        typer.echo(f"{row.change:8} {row.id}  {row.status}  [{flag}]  {row.path}")
    for path in report.skipped:
        typer.echo(f"skipped  {path}  (changed on main since the last sync)")
    if dry_run and report.action == "would-open":
        typer.echo(f"\nwould open {report.branch} (auto-merge {'on' if report.auto else 'off'}):\n")
        typer.echo(report.body)
    summary = {
        "nothing": "nothing to publish",
        "killed": f"killed ({report.detail}): nothing done",
        "holding": f"holding counter-only changes: {report.detail}",
        "waiting": f"waiting: {report.detail}; changes stay for the next run",
        "would-open": f"dry run: would open {report.branch}",
        "opened": f"opened {report.url} on {report.branch}"
        + (" (auto-merge on)" if report.auto else " (needs review)")
        + (f"; {report.detail}" if report.detail else ""),
        "refused": f"refused: {report.detail}",
    }[report.action]
    typer.echo(summary, err=True)
    raise typer.Exit(EXIT_REFUSED if report.action == "refused" else EXIT_OK)
