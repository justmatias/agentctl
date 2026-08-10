from collections.abc import Generator

import pytest

from agentctl.utils import logger


@pytest.fixture
def capture_logs() -> Generator[list[str]]:
    output = []
    handler_id = logger.add(output.append)
    yield output
    logger.remove(handler_id)


@pytest.fixture(
    params=[
        "debug",
        "info",
        "warning",
        "error",
        "critical",
    ]
)
def log_method(request: pytest.FixtureRequest) -> str:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture
def message() -> str:
    return "Test message"
