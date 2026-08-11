"""CLI entry point: subcommand scaffolding only, no real behavior yet (ROADMAP.md PR 0.5).

Surface matches SPECS.md §9 and the Phase-1 roadmap: `status`, `why`,
`project add/list/remove`, `snapshot`, `restore`, `ui`.
"""

import typer

app = typer.Typer(
    name="agentctl",
    help="Local-first control center for AI coding agents.",
    no_args_is_help=True,
)
project_app = typer.Typer(help="Register, list, and unregister project paths (SPECS.md §7.9).")
app.add_typer(project_app, name="project")


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON instead of text."
    ),
) -> None:
    ctx.obj = {"json": json_output}


def _not_yet_implemented(ctx: typer.Context, command: str) -> None:
    if ctx.obj["json"]:
        typer.echo(f'{{"command": "{command}", "status": "not_yet_implemented"}}')
    else:
        typer.echo(f"{command}: not yet implemented")


@app.command()
def status(ctx: typer.Context) -> None:
    """Cross-harness overview: counts per type/source, needs-review queue, drift/conflict."""
    _not_yet_implemented(ctx, "status")


@app.command()
def why(ctx: typer.Context, key: str) -> None:
    """Print the precedence stack for KEY, top to bottom, winner marked."""
    _not_yet_implemented(ctx, f"why {key}")


@project_app.command("add")
def project_add(ctx: typer.Context, path: str) -> None:
    """Register PATH (must be absolute) as a tracked project."""
    _not_yet_implemented(ctx, f"project add {path}")


@project_app.command("list")
def project_list(ctx: typer.Context) -> None:
    """List every registered project."""
    _not_yet_implemented(ctx, "project list")


@project_app.command("remove")
def project_remove(ctx: typer.Context, path: str) -> None:
    """Unregister PATH. Never touches files on disk."""
    _not_yet_implemented(ctx, f"project remove {path}")


@app.command()
def snapshot(ctx: typer.Context) -> None:
    """Export, run the redaction gate, and commit — printing the redaction report first."""
    _not_yet_implemented(ctx, "snapshot")


@app.command()
def restore(ctx: typer.Context) -> None:
    """Apply a bundle onto this host from a reviewable, confirmed plan."""
    _not_yet_implemented(ctx, "restore")


@app.command()
def ui(ctx: typer.Context) -> None:
    """Launch the local web UI in your default browser."""
    _not_yet_implemented(ctx, "ui")
