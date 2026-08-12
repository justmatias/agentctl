from typer.testing import CliRunner

from agentctl.cli import app


def test_top_level_help_lists_every_planned_command(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("status", "why", "project", "snapshot", "restore", "ui"):
        assert command in result.output


def test_project_help_lists_its_subcommands(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["project", "--help"])

    assert result.exit_code == 0
    for subcommand in ("add", "list", "remove"):
        assert subcommand in result.output


def test_status(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_why(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["why", "mcpServers.github"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_project_add(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["project", "add", "/some/project"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_project_list(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["project", "list"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_project_remove(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["project", "remove", "/some/project"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_snapshot(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["snapshot"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_restore(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["restore"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_ui(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["ui"])

    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_json_flag_produces_json_shaped_output(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--json", "status"])

    assert result.exit_code == 0
    assert '"status": "not_yet_implemented"' in result.output
