from collections.abc import Generator

import pytest

from agentctl.storage import Database


@pytest.fixture
def database() -> Generator[Database]:
    database = Database(":memory:")
    try:
        yield database
    finally:
        database.close()
