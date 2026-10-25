"""`apifacts pages build`: regenerate `pages/` from the registry, or `--check` it (CI)."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Static fact pages under pages/.", no_args_is_help=True)

EXIT_OK, EXIT_STALE, EXIT_USAGE = 0, 1, 2


def _version(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        if len(value) == 10 and date.fromisoformat(value).isoformat() == value:
            return value
    except ValueError:
        pass
    raise typer.BadParameter("expected a calendar date YYYY-MM-DD")


@app.command()
def build(
    root: Annotated[
        Path, typer.Option(help="Repository root: services/ and facts/ are read from it.")
    ] = Path("."),
    out: Annotated[
        Path | None, typer.Option(help="Output directory; default: <root>/pages.")
    ] = None,
    check: Annotated[
        bool,
        typer.Option("--check", help="Write nothing; exit 1 if --out differs from the registry."),
    ] = False,
    registry_version: Annotated[
        str | None,
        typer.Option(
            callback=_version, help="YYYY-MM-DD; default: the latest date in the facts."
        ),
    ] = None,
) -> None:
    """Generate the fact pages: same registry in, same bytes out.

    Exit codes: 0 written / up to date, 1 out of date (--check) or unreadable registry, 2 usage.
    """
    from apifacts.pages import PagesError
    from apifacts.pages.build import build_pages, load_registry, sync
    from apifacts.pages.templates import plural

    out = out if out is not None else root / "pages"
    try:
        pages = build_pages(*load_registry(root), version=registry_version)
        report = sync(out, pages, check=check)
    except PagesError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_STALE) from None
    if check:
        for label, paths in (
            ("changed", report.changed),
            ("missing", report.missing),
            ("extra", report.extra),
        ):
            for rel in paths:
                typer.echo(f"{label}: {rel}")
        if not report.clean:
            typer.echo(f"{out} is out of date: run `apifacts pages build`", err=True)
            raise typer.Exit(EXIT_STALE)
        typer.echo(f"ok: {out} is up to date ({plural(len(pages), 'page')})", err=True)
        return
    written = len(report.changed) + len(report.missing)
    counts = f"{written} written, {len(report.extra)} removed"
    typer.echo(f"{out}: {plural(len(pages), 'page')} ({counts})", err=True)
