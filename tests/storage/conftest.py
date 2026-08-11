from collections.abc import Generator

import pytest

from agentctl.storage import Database


@pytest.fixture
def database() -> Generator[Database]:
    db = Database(":memory:")
    try:
        yield db
    finally:
        db.close()
