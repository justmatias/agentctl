import json
from pathlib import Path

import pytest

from agentctl.writes import merge_json_keys


class TestMergeJsonKeys:
    @staticmethod
    def test_creates_file_when_missing(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"

        merge_json_keys(target, {"mcpServers": {"github": {"command": "npx"}}})

        assert json.loads(target.read_text()) == {
            "mcpServers": {"github": {"command": "npx"}}
        }

    @staticmethod
    def test_unrelated_keys_survive_a_write(tmp_path: Path) -> None:
        """ROADMAP.md PR 0.3 done-when: unrelated keys in settings.json
        survive a write untouched."""
        target = tmp_path / "settings.json"
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

    @staticmethod
    def test_preserves_key_order(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(json.dumps({"b": 1, "a": 2, "mcpServers": {}}))

        merge_json_keys(target, {"mcpServers": {"github": {}}})

        assert list(json.loads(target.read_text()).keys()) == ["b", "a", "mcpServers"]

    @staticmethod
    def test_new_keys_are_appended(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(json.dumps({"theme": "dark"}))

        merge_json_keys(target, {"mcpServers": {}})

        assert list(json.loads(target.read_text()).keys()) == ["theme", "mcpServers"]

    @staticmethod
    def test_raises_when_root_is_not_an_object(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(json.dumps(["not", "an", "object"]))

        with pytest.raises(TypeError):
            merge_json_keys(target, {"mcpServers": {}})
