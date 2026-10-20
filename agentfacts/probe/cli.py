"""`agentfacts probe run|list` (docs/specs/04-probe-runner.md).

Exit codes: 0 tick done (assertion failures are data, the kill switch is not an error), 1 invalid or
refused probes, 2 usage error.
"""

from pathlib import Path
from typing import Annotated

import typer

from agentfacts.probe.runner import (
    DEFAULT_VANTAGE,
    TickOptions,
    TickReport,
    probe_status,
    rfc3339_epoch,
    run_tick,
)

EXIT_OK, EXIT_INVALID, EXIT_USAGE = 0, 1, 2

app = typer.Typer(
    help="Run declarative probes against vendor APIs and record what they show.",
    no_args_is_help=True,
)

Root = Annotated[Path, typer.Option(help="Repository root (services/, probes/, facts/, ops/KILL).")]
StateDir = Annotated[
    Path | None,
    typer.Option(help="Where results.jsonl and probe-state.sqlite live; default <root>/var."),
]
Vantage = Annotated[str, typer.Option(help="Name of this runner's network vantage point.")]


def _summary(report: TickReport) -> str:
    n = report.counts
    rest = f"{n['skipped_no_key']} skipped:no_key, {n['not_due']} not due, {n['deferred']} deferred"
    if report.results_path is None:
        refused = f", {n['refused']} refused" if n["refused"] else ""
        return f"dry run: {n['would_run']} would run, {rest}{refused}"
    ran = n["pass"] + n["fail"] + n["error"]
    return (
        f"tick: {ran} run ({n['pass']} pass, {n['fail']} fail, {n['error']} error), {rest}; "
        f"results: {report.results_path}"
    )


@app.command("run")
def run(
    run_all: Annotated[
        bool, typer.Option("--all/--due", help="Run every probe, or only due ones (default).")
    ] = False,
    max_probes: Annotated[int, typer.Option("--max", min=0, help="Probes per tick.")] = 50,
    max_requests: Annotated[
        int, typer.Option("--max-requests", min=0, help="HTTP requests per tick.")
    ] = 50,
    vantage: Vantage = DEFAULT_VANTAGE,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Plan only: no request, no key read, no write.")
    ] = False,
    root: Root = Path("."),
    state_dir: StateDir = None,
) -> None:
    """Run one tick: due probes (or --all), at most --max, results to results.jsonl."""
    try:
        options = TickOptions(run_all=run_all, max_probes=max_probes, max_requests=max_requests,
                              vantage=vantage, dry_run=dry_run)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    report = run_tick(root, state_dir or root / "var", options)
    if report.busy:
        typer.echo("another tick is running (probe.lock): nothing to do", err=True)
        raise typer.Exit(EXIT_OK)
    for problem in report.problems:
        typer.echo(str(problem), err=True)
    for line in report.lines:
        typer.echo(f"{line.outcome} {line.probe_id}" + (f" — {line.detail}" if line.detail else ""))
    if report.killed:
        started = report.counts["pass"] + report.counts["fail"] + report.counts["error"]
        what = "stopped before the next probe" if started else "no requests"
        typer.echo(f"kill switch on ({report.killed}): {what}", err=True)
    else:
        typer.echo(_summary(report), err=True)
    raise typer.Exit(EXIT_OK if report.ok else EXIT_INVALID)


@app.command("list")
def list_probes(
    vantage: Vantage = DEFAULT_VANTAGE,
    root: Root = Path("."),
    state_dir: StateDir = None,
) -> None:
    """One line per probe: env, requests, key presence, last run, due or wait."""
    try:
        statuses, problems = probe_status(root, state_dir or root / "var", vantage)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    for problem in problems:
        typer.echo(str(problem), err=True)
    for s in statuses:
        last = f"{rfc3339_epoch(s.last_run[0])} {s.last_run[1]}" if s.last_run else "never"
        due = "due" if s.wait_s == 0 else f"in {s.wait_s}s"
        typer.echo(f"{s.probe_id} {s.env} {s.requests}req key:{s.key} last:{last} {due}")
    raise typer.Exit(EXIT_INVALID if problems else EXIT_OK)
