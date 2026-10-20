"""Command-line entry point: `agentfacts <command>`."""

import typer

from agentfacts import __version__

app = typer.Typer(
    help="agent-facts: verified facts about machine interfaces for AI agents.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Root callback: keeps `version` a subcommand while it is the only one."""


@app.command()
def version() -> None:
    """Print the agentfacts version."""
    typer.echo(__version__)
