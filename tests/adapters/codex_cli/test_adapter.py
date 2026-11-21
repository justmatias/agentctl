from pathlib import Path

import pytest

from agentctl.adapters import (
    CodexCliAdapter,
    SourceAdapter,
    WalkUpBehavior,
    WorkflowTargetForm,
)
from agentctl.adapters.codex_cli import default_codex_home
from agentctl.domain import (
    Extension,
    ExtensionType,
    LayerOrigin,
    McpServerConfig,
    MemoryFileConfig,
    Scope,
    Source,
)

COMMAND_LINE_ARGUMENTS = "(command-line arguments)"


def test_adapter_implements_the_source_adapter_protocol(
    adapter: CodexCliAdapter,
) -> None:
    assert isinstance(adapter, SourceAdapter)
    assert adapter.source == Source.CODEX_CLI


def test_locate_global_config_finds_nothing_when_nothing_installed(
    nothing_installed_adapter: CodexCliAdapter,
) -> None:
    assert nothing_installed_adapter.locate_global_config() == []


def test_locate_project_config_finds_nothing_when_nothing_installed(
    nothing_installed_adapter: CodexCliAdapter,
    nothing_installed_project_root: Path,
) -> None:
    located = nothing_installed_adapter.locate_project_config(
        nothing_installed_project_root
    )

    assert located == []


def test_locate_global_config_finds_every_global_scope_file(
    global_only_adapter: CodexCliAdapter,
) -> None:
    codex_home = global_only_adapter.codex_home

    assert set(global_only_adapter.locate_global_config()) == {
        codex_home / "config.toml",
        codex_home / "AGENTS.md",
    }


def test_locate_global_config_finds_the_instructions_override(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    codex_home = global_and_project_adapter.codex_home

    assert set(global_and_project_adapter.locate_global_config()) == {
        codex_home / "config.toml",
        codex_home / "AGENTS.override.md",
        codex_home / "AGENTS.md",
    }


@pytest.mark.usefixtures("_write_machine_wide_configs")
def test_locate_global_config_finds_administrator_owned_config(
    adapter: CodexCliAdapter,
) -> None:
    assert set(adapter.locate_global_config()) == {
        adapter.managed_config_path,
        adapter.system_config_path,
    }


def test_locate_project_config_finds_every_project_scope_file(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    project_root = global_and_project_project_root

    located = set(global_and_project_adapter.locate_project_config(project_root))

    assert located == {
        project_root / ".codex" / "config.toml",
        project_root / "AGENTS.md",
    }


def test_parse_extracts_mcp_server_from_config_toml(
    global_only_adapter: CodexCliAdapter,
) -> None:
    extensions = global_only_adapter.parse(
        global_only_adapter.codex_home / "config.toml"
    )

    assert len(extensions) == 1
    extension = extensions[0]
    assert extension.name == "context7"
    assert extension.origin_harness == Source.CODEX_CLI
    assert extension.type == ExtensionType.MCP_SERVER
    canonical = extension.canonical_config
    assert isinstance(canonical, McpServerConfig)
    assert canonical.command == "npx"
    # A '#' inside a quoted string opens no comment, and a trailing comment is
    # never part of the value before it.
    assert canonical.args == ["-y", "@upstash/context7-mcp", "--tag=#latest"]
    # `env` is a nested `[mcp_servers.context7.env]` table, not an inline one.
    assert canonical.env == {"CONTEXT7_API_KEY": "${CONTEXT7_API_KEY}"}


def test_parse_ignores_tables_that_are_not_mcp_servers(
    global_only_adapter: CodexCliAdapter,
) -> None:
    """Top-level keys, arrays of tables (`[[hooks.SessionStart]]`) and nested
    tables under quoted keys (`[projects."/path"]`) are not MCP servers."""
    extensions = global_only_adapter.parse(
        global_only_adapter.codex_home / "config.toml"
    )

    assert [extension.name for extension in extensions] == ["context7"]


def test_parse_leaves_the_file_exactly_as_it_was_on_disk(
    global_only_adapter: CodexCliAdapter,
) -> None:
    """Reading is non-destructive: comments, ordering and Codex-only keys the
    canonical shape has no room for survive a parse untouched."""
    config_path = global_only_adapter.codex_home / "config.toml"
    before = config_path.read_bytes()

    global_only_adapter.parse(config_path)

    assert config_path.read_bytes() == before


def test_parse_extracts_mcp_server_with_remote_transport(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    config_path = global_and_project_project_root / ".codex" / "config.toml"

    extensions = global_and_project_adapter.parse(config_path)

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, McpServerConfig)
    assert canonical.url == "https://example.com/mcp"
    assert canonical.headers == {"X-Example-Region": "us-east-1"}


def test_parse_config_without_mcp_servers_yields_no_extensions(
    adapter: CodexCliAdapter, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('model = "gpt-5-codex"\n')

    assert not adapter.parse(config_path)


def test_parse_extracts_project_instructions_file(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    extensions = global_and_project_adapter.parse(
        global_and_project_project_root / "AGENTS.md"
    )

    assert len(extensions) == 1
    extension = extensions[0]
    assert extension.name == "AGENTS.md"
    canonical = extension.canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    # AGENTS.md is authored, never accumulated by the agent.
    assert canonical.is_persistent_memory is False
    assert "Run `make test` before committing." in canonical.content


def test_parse_extracts_instructions_override_file(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    override_path = global_and_project_adapter.codex_home / "AGENTS.override.md"

    extensions = global_and_project_adapter.parse(override_path)

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert "Ship nothing to production this week." in canonical.content


def test_parse_malformed_toml_is_non_fatal(
    malformed_toml_adapter: CodexCliAdapter,
) -> None:
    assert not malformed_toml_adapter.parse(
        malformed_toml_adapter.codex_home / "config.toml"
    )


def test_parse_missing_file_is_non_fatal(
    adapter: CodexCliAdapter, tmp_path: Path
) -> None:
    assert not adapter.parse(tmp_path / "does-not-exist.toml")


def test_parse_skips_malformed_config_content(
    adapter: CodexCliAdapter, malformed_config_path: Path
) -> None:
    assert not adapter.parse(malformed_config_path)


def test_parse_unrecognized_file_type_returns_empty_list(
    adapter: CodexCliAdapter, tmp_path: Path
) -> None:
    unknown_path = tmp_path / "notes.txt"
    unknown_path.write_text("just some notes")

    assert not adapter.parse(unknown_path)


def test_serialize_mcp_server_round_trips_through_parse(
    adapter: CodexCliAdapter, tmp_path: Path, mcp_server_extension: Extension
) -> None:
    rendered = adapter.serialize(mcp_server_extension)
    config_path = tmp_path / "config.toml"
    config_path.write_text(rendered)

    reparsed = adapter.parse(config_path)

    assert len(reparsed) == 1
    assert reparsed[0].name == mcp_server_extension.name
    assert reparsed[0].canonical_config == mcp_server_extension.canonical_config


def test_serialize_memory_file_returns_raw_content(adapter: CodexCliAdapter) -> None:
    canonical = MemoryFileConfig(content="# Hello\n", is_persistent_memory=False)
    extension = Extension(name="AGENTS.md", canonical_config=canonical)

    assert adapter.serialize(extension) == "# Hello\n"


def test_walk_up_behavior(
    adapter: CodexCliAdapter,
    expected_walk_up_behavior: tuple[ExtensionType, WalkUpBehavior],
) -> None:
    extension_type, expected = expected_walk_up_behavior

    assert adapter.walk_up_behavior(extension_type) == expected


def test_capabilities_declares_the_types_and_scopes_codex_has(
    adapter: CodexCliAdapter,
) -> None:
    capabilities = adapter.capabilities

    assert capabilities.source == Source.CODEX_CLI
    assert capabilities.extension_types == frozenset({
        ExtensionType.MCP_SERVER,
        ExtensionType.MEMORY_FILE,
    })
    # Codex has no gitignored per-project layer, so Scope.LOCAL is unused.
    assert capabilities.scopes == frozenset(Scope) - {Scope.LOCAL}
    assert capabilities.workflow_target_forms == frozenset({WorkflowTargetForm.SKILL})


def test_precedence_chain_ranks_every_layer_for_a_project(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    adapter = global_and_project_adapter
    project_root = global_and_project_project_root

    chain = adapter.precedence_chain(project_root)

    assert chain.source == Source.CODEX_CLI
    assert [(layer.scope, layer.file_path) for layer in chain.layers] == [
        (Scope.MANAGED, str(adapter.managed_config_path)),
        (Scope.GLOBAL, COMMAND_LINE_ARGUMENTS),
        (Scope.PROJECT, str(project_root / ".codex" / "config.toml")),
        (Scope.USER, str(adapter.user_config_path)),
        (Scope.MANAGED, str(adapter.system_config_path)),
        (Scope.PROJECT, str(project_root / "AGENTS.override.md")),
        (Scope.PROJECT, str(project_root / "AGENTS.md")),
        (Scope.USER, str(adapter.codex_home / "AGENTS.override.md")),
        (Scope.USER, str(adapter.codex_home / "AGENTS.md")),
    ]
    assert [layer.order_rank for layer in chain.layers] == list(range(1, 10))  # type: ignore[union-attr]


def test_precedence_chain_tags_project_layers_with_their_origin(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    chain = global_and_project_adapter.precedence_chain(global_and_project_project_root)

    project_layers = [layer for layer in chain.layers if layer.scope == Scope.PROJECT]
    assert project_layers
    assert all(
        layer.origin == LayerOrigin.REGISTERED_PROJECT for layer in project_layers
    )


def test_precedence_chain_omits_project_layers_for_the_global_view(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    chain = global_and_project_adapter.precedence_chain(None)

    assert Scope.PROJECT not in {layer.scope for layer in chain.layers}
    assert [layer.order_rank for layer in chain.layers] == list(range(1, 7))  # type: ignore[union-attr]


def test_command_line_argument_layer_can_never_resolve(
    adapter: CodexCliAdapter,
) -> None:
    """`-c` overrides outrank every file but the managed one, and never touch
    disk, so a static scan can never name one as the winner."""
    chain = adapter.precedence_chain(None)

    command_line_layer = next(
        layer for layer in chain.layers if layer.file_path == COMMAND_LINE_ARGUMENTS
    )
    assert command_line_layer.order_rank == 2  # type: ignore[union-attr]
    assert command_line_layer.exists is False
    assert command_line_layer.resolves is False


@pytest.mark.usefixtures("_write_machine_wide_configs")
def test_precedence_chain_reports_administrator_owned_config_as_existing(
    adapter: CodexCliAdapter,
) -> None:
    chain = adapter.precedence_chain(None)

    managed_layers = [layer for layer in chain.layers if layer.scope == Scope.MANAGED]
    assert [layer.file_path for layer in managed_layers] == [
        str(adapter.managed_config_path),
        str(adapter.system_config_path),
    ]
    assert all(layer.exists and layer.resolves for layer in managed_layers)


def test_instructions_override_shadows_the_agents_file_beside_it(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    """Codex reads at most one instructions file per directory, so the user's
    AGENTS.md exists without resolving while the override sits next to it."""
    adapter = global_and_project_adapter

    chain = adapter.precedence_chain(None)

    override_layer, agents_layer = (
        layer
        for layer in chain.layers
        if layer.scope == Scope.USER and "AGENTS" in layer.file_path
    )
    assert override_layer.exists is True
    assert override_layer.resolves is True
    assert agents_layer.exists is True
    assert agents_layer.resolves is False


def test_agents_file_resolves_when_no_override_shadows_it(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    chain = global_and_project_adapter.precedence_chain(global_and_project_project_root)

    override_layer, agents_layer = (
        layer
        for layer in chain.layers
        if layer.scope == Scope.PROJECT and "AGENTS" in layer.file_path
    )
    assert override_layer.exists is False
    assert override_layer.resolves is False
    assert agents_layer.exists is True
    assert agents_layer.resolves is True


def test_managed_config_path_is_operating_system_specific(
    adapter: CodexCliAdapter, expected_managed_config_path: Path
) -> None:
    assert adapter.managed_config_path == expected_managed_config_path


def test_default_codex_home_honors_the_codex_home_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "elsewhere"))

    assert default_codex_home() == tmp_path / "elsewhere"


def test_default_codex_home_falls_back_to_the_dot_codex_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODEX_HOME", raising=False)

    assert default_codex_home() == Path.home() / ".codex"
