import json
from pathlib import Path

import pytest

from agentctl.writes import merge_json_keys


def test_creates_file_when_missing(target: Path) -> None:
    merge_json_keys(target, {"mcpServers": {"github": {"command": "npx"}}})

    assert json.loads(target.read_text()) == {
        "mcpServers": {"github": {"command": "npx"}}
    }


def test_unrelated_keys_survive_a_write(target: Path) -> None:
    """ROADMAP.md PR 0.3 done-when: unrelated keys in settings.json
    survive a write untouched."""
    target.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(git status)"]},
                "theme": "dark",
                "mcpServers": {"old-server": {"command": "old"}},
            },
            indent=2,
        )
    )

    merge_json_keys(target, {"mcpServers": {"github": {"command": "npx"}}})

    result = json.loads(target.read_text())
    assert result["permissions"] == {"allow": ["Bash(git status)"]}
    assert result["theme"] == "dark"
    assert result["mcpServers"] == {"github": {"command": "npx"}}


def test_preserves_key_order(target: Path) -> None:
    target.write_text(json.dumps({"b": 1, "a": 2, "mcpServers": {}}))

    merge_json_keys(target, {"mcpServers": {"github": {}}})

    assert list(json.loads(target.read_text()).keys()) == ["b", "a", "mcpServers"]


def test_new_keys_are_appended(target: Path) -> None:
    target.write_text(json.dumps({"theme": "dark"}))

    merge_json_keys(target, {"mcpServers": {}})

    assert list(json.loads(target.read_text()).keys()) == ["theme", "mcpServers"]


def test_raises_when_root_is_not_an_object(target: Path) -> None:
    target.write_text(json.dumps(["not", "an", "object"]))

    with pytest.raises(TypeError):
        merge_json_keys(target, {"mcpServers": {}})
