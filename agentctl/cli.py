"""CLI entry point: subcommand scaffolding only, no real behavior yet (ROADMAP.md PR 0.5).

Surface matches SPECS.md §9 and the Phase-1 roadmap: `status`, `why`,
`project add/list/remove`, `snapshot`, `restore`, `ui`.
"""

import json

import typer

app = typer.Typer(
    name="agentctl",
    help="Local-first control center for AI coding agents.",
    no_args_is_help=True,
)
project_app = typer.Typer(
    help="Register, list, and unregister project paths (SPECS.md §7.9)."
)
app.add_typer(project_app, name="project")


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON instead of text."
    ),
) -> None:
    ctx.obj = {"json": json_output}


@app.command()
def status(ctx: typer.Context) -> None:
    """Cross-harness overview: counts per type/source, needs-review queue, drift/conflict."""
    if ctx.obj["json"]:
        typer.echo(json.dumps({"command": "status", "status": "not_yet_implemented"}))
    else:
        typer.echo("status: not yet implemented")


@app.command()
def why(ctx: typer.Context, key: str) -> None:
    """Print the precedence stack for KEY, top to bottom, winner marked."""
    command = f"why {key}"
    if ctx.obj["json"]:
        typer.echo(json.dumps({"command": command, "status": "not_yet_implemented"}))
    else:
        typer.echo(f"{command}: not yet implemented")


@project_app.command("add")
def project_add(ctx: typer.Context, path: str) -> None:
    """Register PATH (must be absolute) as a tracked project."""
    command = f"project add {path}"
    if ctx.obj["json"]:
        typer.echo(json.dumps({"command": command, "status": "not_yet_implemented"}))
    else:
        typer.echo(f"{command}: not yet implemented")


@project_app.command("list")
def project_list(ctx: typer.Context) -> None:
    """List every registered project."""
    if ctx.obj["json"]:
        typer.echo(
            json.dumps({"command": "project list", "status": "not_yet_implemented"})
        )
    else:
        typer.echo("project list: not yet implemented")


@project_app.command("remove")
def project_remove(ctx: typer.Context, path: str) -> None:
    """Unregister PATH. Never touches files on disk."""
    command = f"project remove {path}"
    if ctx.obj["json"]:
        typer.echo(json.dumps({"command": command, "status": "not_yet_implemented"}))
    else:
        typer.echo(f"{command}: not yet implemented")


@app.command()
def snapshot(ctx: typer.Context) -> None:
    """Export, run the redaction gate, and commit — printing the redaction report first."""
    if ctx.obj["json"]:
        typer.echo(
            json.dumps({"command": "snapshot", "status": "not_yet_implemented"})
        )
    else:
        typer.echo("snapshot: not yet implemented")


@app.command()
def restore(ctx: typer.Context) -> None:
    """Apply a bundle onto this host from a reviewable, confirmed plan."""
    if ctx.obj["json"]:
        typer.echo(json.dumps({"command": "restore", "status": "not_yet_implemented"}))
    else:
        typer.echo("restore: not yet implemented")


@app.command()
def ui(ctx: typer.Context) -> None:
    """Launch the local web UI in your default browser."""
    if ctx.obj["json"]:
        typer.echo(json.dumps({"command": "ui", "status": "not_yet_implemented"}))
    else:
        typer.echo("ui: not yet implemented")
