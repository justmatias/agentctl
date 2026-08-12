from collections.abc import Generator

import pytest
from typer.testing import CliRunner

from agentctl.storage import Database

pytest_plugins = ["tests.polyfactory", "tests.factories"]


@pytest.fixture
def database() -> Generator[Database]:
    database = Database(":memory:")
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()
