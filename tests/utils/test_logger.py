from collections.abc import Generator

from agentctl.utils import logger


def test_log(
    capture_logs: Generator[list[str]], log_method: str, message: str
) -> None:
    getattr(logger, log_method)(message)
    logs = list(capture_logs)
    assert message in logs[0]
    assert log_method.upper() in logs[0]
