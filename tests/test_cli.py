from typer.testing import CliRunner

from agentctl.cli import app

runner = CliRunner()


def test_top_level_help_lists_every_planned_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("status", "why", "project", "snapshot", "restore", "ui"):
        assert command in result.output


def test_project_help_lists_its_subcommands() -> None:
    result = runner.invoke(app, ["project", "--help"])

    assert result.exit_code == 0
    for subcommand in ("add", "list", "remove"):
        assert subcommand in result.output


def test_status() -> None:
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_why() -> None:
    result = runner.invoke(app, ["why", "mcpServers.github"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_project_add() -> None:
    result = runner.invoke(app, ["project", "add", "/some/project"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_project_list() -> None:
    result = runner.invoke(app, ["project", "list"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_project_remove() -> None:
    result = runner.invoke(app, ["project", "remove", "/some/project"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_snapshot() -> None:
    result = runner.invoke(app, ["snapshot"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_restore() -> None:
    result = runner.invoke(app, ["restore"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_ui() -> None:
    result = runner.invoke(app, ["ui"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_json_flag_produces_json_shaped_output() -> None:
    result = runner.invoke(app, ["--json", "status"])

    assert result.exit_code == 0
    assert '"status": "not_yet_implemented"' in result.output
