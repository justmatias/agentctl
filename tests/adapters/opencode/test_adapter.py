import json
from pathlib import Path

import pytest

from agentctl.adapters import OpenCodeAdapter
from agentctl.domain import McpServerConfig, MemoryFileConfig, SkillConfig, Source


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        (
            {
                "type": "local",
                "command": ["tool", "--stdio"],
                "environment": {"MODE": "test"},
            },
            McpServerConfig(command="tool", args=["--stdio"], env={"MODE": "test"}),
        ),
        (
            {
                "type": "remote",
                "url": "https://example.com/mcp",
                "headers": {"X-Mode": "test"},
            },
            McpServerConfig(url="https://example.com/mcp", headers={"X-Mode": "test"}),
        ),
    ],
    ids=["local", "remote"],
)
def test_parses_canonical_mcp_server_when_global_config_is_present(
    tmp_path: Path, entry: dict[str, object], expected: McpServerConfig
) -> None:
    config = tmp_path / "opencode.json"
    config.write_text(json.dumps({"mcp": {"example": entry}}))
    adapter = OpenCodeAdapter(config_directory=tmp_path)

    (path,) = adapter.locate_global_config()
    (extension,) = adapter.parse(path)

    assert extension.name == "example"
    assert extension.origin_harness == Source.OPENCODE
    assert extension.canonical_config == expected


def test_skips_invalid_mcp_entry_when_valid_entry_shares_config(tmp_path: Path) -> None:
    config = tmp_path / "opencode.json"
    config.write_text(
        '{"mcp": {"invalid": {"type": "local", "command": []},'
        '"valid": {"type": "local", "command": ["tool"]}}}'
    )

    assert [
        extension.name
        for extension in OpenCodeAdapter(config_directory=tmp_path).parse(config)
    ] == ["valid"]


def test_discovers_canonical_skill_when_global_skill_is_installed(
    tmp_path: Path,
) -> None:
    skill = tmp_path / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: Review code\n---\nReview.\n")
    adapter = OpenCodeAdapter(config_directory=tmp_path)

    (path,) = adapter.locate_global_config()
    (extension,) = adapter.parse(path)

    assert extension.name == "review"
    assert extension.canonical_config == SkillConfig(
        description="Review code", body="Review."
    )


def test_discovers_instructions_when_project_has_agents_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    (project / ".git" / "HEAD").touch()
    (project / "AGENTS.md").write_text("Project instructions\n")
    adapter = OpenCodeAdapter(config_directory=tmp_path / "config")

    (path,) = adapter.locate_project_config(project)
    (extension,) = adapter.parse(path)

    assert extension.name == "AGENTS.md"
    assert extension.canonical_config == MemoryFileConfig(
        content="Project instructions\n", is_persistent_memory=False
    )


def test_parse_returns_no_extensions_when_config_is_malformed(tmp_path: Path) -> None:
    config = tmp_path / "opencode.json"
    config.write_text('{"mcp":')
    assert not OpenCodeAdapter(config_directory=tmp_path).parse(config)


def test_chain_orders_native_files_when_git_project_is_nested(tmp_path: Path) -> None:
    root = tmp_path / "project"
    nested = root / "nested"
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "HEAD").touch()
    for directory in (root, nested):
        (directory / ".opencode").mkdir(parents=True)
        (directory / ".opencode" / "opencode.json").write_text("{}")
        (directory / "opencode.json").write_text("{}")
        (directory / "AGENTS.md").touch()

    adapter = OpenCodeAdapter(config_directory=tmp_path / "config")
    layers = adapter.precedence_chain(nested).layers

    assert [Path(layer.file_path) for layer in layers if layer.exists] == [
        root / ".opencode" / "opencode.json",
        nested / ".opencode" / "opencode.json",
        nested / "opencode.json",
        root / "opencode.json",
        nested / "AGENTS.md",
        root / "AGENTS.md",
    ]


def test_locates_parent_instructions_when_project_is_outside_git(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "nested"
    directory.mkdir()
    instructions = tmp_path / "AGENTS.md"
    instructions.touch()

    adapter = OpenCodeAdapter(config_directory=tmp_path / "config")

    assert instructions in adapter.locate_project_config(directory)


def test_parse_skips_skill_when_name_is_not_text(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: [unexpected]\ndescription: Review code\n---\nReview.\n"
    )

    assert not OpenCodeAdapter(config_directory=tmp_path).parse(skill)


def test_parses_mcp_server_when_json_has_comments_and_trailing_commas(
    tmp_path: Path,
) -> None:
    config = tmp_path / "opencode.json"
    config.write_text(
        """
        {
          // The URL contains a literal double slash.
          "mcp": {
            "example": {"type": "remote", "url": "https://example.com/mcp",},
          },
        }
        """
    )

    (extension,) = OpenCodeAdapter(config_directory=tmp_path).parse(config)

    assert extension.canonical_config == McpServerConfig(url="https://example.com/mcp")
