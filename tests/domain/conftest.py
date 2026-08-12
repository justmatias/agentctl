from typing import cast

import pytest
from pydantic import BaseModel

from agentctl.domain import McpServerConfig, MemoryFileConfig, SkillConfig


def assert_round_trips(model: BaseModel) -> None:
    rebuilt = type(model).model_validate_json(model.model_dump_json())
    assert rebuilt == model


@pytest.fixture(
    params=[
        McpServerConfig(command="npx", args=["-y", "github-mcp"]),
        MemoryFileConfig(content="# Notes", is_persistent_memory=True),
        SkillConfig(description="Does a thing", body="# Skill"),
    ]
)
def canonical_config(
    request: pytest.FixtureRequest,
) -> McpServerConfig | MemoryFileConfig | SkillConfig:
    return cast(McpServerConfig | MemoryFileConfig | SkillConfig, request.param)
