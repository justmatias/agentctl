from pathlib import Path

from agentctl.adapters import OpenCodeAdapter
from agentctl.domain import McpServerConfig, MemoryFileConfig, SkillConfig, Source


def test_discovers_canonical_extensions_when_opencode_is_configured(
    tmp_path: Path,
) -> None:
    global_config = tmp_path / "config" / "opencode"
    skill = global_config / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: Review code\n---\nReview.\n")
    (global_config / "opencode.json").write_text(
        """{"mcp": {
            "local": {"type": "local", "command": ["tool", "--stdio"],
                      "environment": {"MODE": "test"}},
            "remote": {"type": "remote", "url": "https://example.com/mcp",
                       "headers": {"X-Mode": "test"}},
            "invalid": {"type": "local", "command": []}
        }}"""
    )
    project = tmp_path / "project"
    project.mkdir()
    instructions = project / "AGENTS.md"
    instructions.write_text("Project instructions\n")

    adapter = OpenCodeAdapter(config_directory=global_config)
    paths = adapter.locate_global_config() + adapter.locate_project_config(project)
    extensions = [extension for path in paths for extension in adapter.parse(path)]

    assert {extension.origin_harness for extension in extensions} == {Source.OPENCODE}
    assert {extension.name: extension.canonical_config for extension in extensions} == {
        "local": McpServerConfig(
            command="tool", args=["--stdio"], env={"MODE": "test"}
        ),
        "remote": McpServerConfig(
            url="https://example.com/mcp", headers={"X-Mode": "test"}
        ),
        "review": SkillConfig(description="Review code", body="Review."),
        "AGENTS.md": MemoryFileConfig(
            content="Project instructions\n", is_persistent_memory=False
        ),
    }


def test_parse_returns_no_extensions_when_config_is_malformed(tmp_path: Path) -> None:
    config = tmp_path / "opencode.json"
    config.write_text('{"mcp":')
    assert OpenCodeAdapter(config_directory=tmp_path).parse(config) == []


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

    assert OpenCodeAdapter(config_directory=tmp_path).parse(skill) == []
