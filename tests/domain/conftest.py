from pydantic import BaseModel


def assert_round_trips(model: BaseModel) -> None:
    rebuilt = type(model).model_validate_json(model.model_dump_json())
    assert rebuilt == model
