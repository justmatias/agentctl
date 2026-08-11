import pytest
from pydantic import BaseModel

from agentctl.domain import Extension
from tests.factories import make_extension


@pytest.fixture
def extension() -> Extension:
    return make_extension()


def assert_round_trips(model: BaseModel) -> None:
    rebuilt = type(model).model_validate_json(model.model_dump_json())
    assert rebuilt == model
