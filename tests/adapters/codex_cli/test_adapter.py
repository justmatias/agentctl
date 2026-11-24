import tomllib
from pathlib import Path

import pytest

from agentctl.adapters import (
    CodexCliAdapter,
    SourceAdapter,
    WalkUpBehavior,
    WorkflowTargetForm,
)
from agentctl.adapters.codex_cli import COMMAND_LINE_ARGUMENTS, default_codex_home
from agentctl.domain import (
    Extension,
    ExtensionType,
    LayerOrigin,
    McpServerConfig,
    MemoryFileConfig,
    Scope,
    Source,
)
from tests.adapters.codex_cli.conftest import NestedProjectFiles


def test_adapter_implements_the_source_protocol_when_instantiated(
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


def test_locate_global_config_finds_user_files_when_present(
    global_only_adapter: CodexCliAdapter,
) -> None:
    codex_home = global_only_adapter.codex_home

    assert set(global_only_adapter.locate_global_config()) == {
        codex_home / "config.toml",
        codex_home / "AGENTS.md",
    }


def test_locate_global_config_omits_base_instructions_when_shadowed(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    codex_home = global_and_project_adapter.codex_home

    assert set(global_and_project_adapter.locate_global_config()) == {
        codex_home / "config.toml",
        codex_home / "AGENTS.override.md",
    }


@pytest.mark.usefixtures("_write_blank_global_override")
def test_locate_global_config_selects_base_when_override_is_blank(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    adapter = global_and_project_adapter

    assert adapter.locate_global_config() == [
        adapter.user_config_path,
        adapter.codex_home / "AGENTS.md",
    ]


@pytest.mark.usefixtures("_write_blank_global_override")
def test_parse_selects_global_base_when_override_is_blank(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    adapter = global_and_project_adapter

    assert adapter.parse(adapter.codex_home / "AGENTS.md")
    assert not adapter.parse(adapter.codex_home / "AGENTS.override.md")


@pytest.mark.usefixtures("_write_machine_wide_configs")
def test_locate_global_config_finds_administrator_owned_config_when_present(
    adapter: CodexCliAdapter,
) -> None:
    assert set(adapter.locate_global_config()) == {
        adapter.managed_config_path,
        adapter.system_config_path,
    }


def test_locate_project_config_finds_project_files_when_present(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    project_root = global_and_project_project_root

    located = set(global_and_project_adapter.locate_project_config(project_root))

    assert located == {
        project_root / ".codex" / "config.toml",
        project_root / "AGENTS.md",
    }


def test_locate_project_config_omits_base_instructions_when_shadowed(
    adapter: CodexCliAdapter, tmp_path: Path
) -> None:
    base = tmp_path / "AGENTS.md"
    override = tmp_path / "AGENTS.override.md"
    base.write_text("Base instructions")
    override.write_text("Override instructions")

    assert adapter.locate_project_config(tmp_path) == [override]


def test_locate_project_config_omits_instructions_when_override_is_blank(
    adapter: CodexCliAdapter, project_with_blank_override: Path
) -> None:
    assert adapter.locate_project_config(project_with_blank_override) == []


def test_parse_omits_project_instructions_when_override_is_blank(
    adapter: CodexCliAdapter, project_with_blank_override: Path
) -> None:
    assert not adapter.parse(project_with_blank_override / "AGENTS.md")
    assert not adapter.parse(project_with_blank_override / "AGENTS.override.md")


@pytest.mark.parametrize(
    ("scope", "override_content", "base_resolves"),
    [(Scope.USER, "", True), (Scope.USER, " \n", True), (Scope.PROJECT, "", False)],
)
def test_precedence_chain_selects_instructions_when_override_is_blank(
    adapter: CodexCliAdapter,
    tmp_path: Path,
    scope: Scope,
    override_content: str,
    base_resolves: bool,
) -> None:
    directory = adapter.codex_home if scope == Scope.USER else tmp_path / "project"
    directory.mkdir()
    override = directory / "AGENTS.override.md"
    override.write_text(override_content)
    base = directory / "AGENTS.md"
    base.write_text("Base instructions")
    project_root = directory if scope == Scope.PROJECT else None

    chain = adapter.precedence_chain(project_root)

    assert [
        (Path(layer.file_path), layer.resolves)
        for layer in chain.layers
        if layer.scope == scope and Path(layer.file_path) in {override, base}
    ] == [(override, False), (base, base_resolves)]


def test_parse_respects_project_shadowing_when_codex_home_is_the_project(
    adapter: CodexCliAdapter,
) -> None:
    adapter.codex_home.mkdir()
    base = adapter.codex_home / "AGENTS.md"
    base.write_text("Global base instructions")
    (adapter.codex_home / "AGENTS.override.md").touch()

    source_adapter: SourceAdapter = adapter
    assert source_adapter.parse(base, scope=Scope.USER)
    assert not source_adapter.parse(base, scope=Scope.PROJECT)


def test_parse_returns_nothing_when_base_instructions_are_shadowed(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    base = global_and_project_adapter.codex_home / "AGENTS.md"

    assert global_and_project_adapter.parse(base) == []


def test_parse_extracts_mcp_server_when_config_toml_declares_one(
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


def test_parse_extracts_only_mcp_servers_when_other_tables_exist(
    global_only_adapter: CodexCliAdapter,
) -> None:
    """Top-level keys, arrays of tables (`[[hooks.SessionStart]]`) and nested
    tables under quoted keys (`[projects."/path"]`) are not MCP servers."""
    extensions = global_only_adapter.parse(
        global_only_adapter.codex_home / "config.toml"
    )

    assert [extension.name for extension in extensions] == ["context7"]


def test_parse_extracts_the_same_mcp_server_when_toml_spells_it_differently(
    adapter: CodexCliAdapter, equivalent_mcp_server_config_path: Path
) -> None:
    extensions = adapter.parse(equivalent_mcp_server_config_path)

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, McpServerConfig)
    assert canonical.command == "npx"
    assert canonical.args == ["-y", "some-mcp"]
    assert canonical.env == {"TOKEN": "secret"}


def test_parse_extracts_remote_transport_when_config_declares_a_url(
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


def test_parse_returns_nothing_when_config_has_no_mcp_servers(
    adapter: CodexCliAdapter, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('model = "gpt-5-codex"\n')

    assert not adapter.parse(config_path)


def test_parse_extracts_project_instructions_when_base_file_exists(
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


def test_parse_extracts_override_instructions_when_override_file_exists(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    override_path = global_and_project_adapter.codex_home / "AGENTS.override.md"

    extensions = global_and_project_adapter.parse(override_path)

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert "Ship nothing to production this week." in canonical.content


def test_parse_loads_instructions_when_utf8_contains_invalid_bytes(
    adapter: CodexCliAdapter, tmp_path: Path
) -> None:
    override = tmp_path / "AGENTS.override.md"
    override.write_bytes(b"Project instructions \xff")

    extensions = adapter.parse(override)

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert canonical.content == "Project instructions \ufffd"


@pytest.mark.usefixtures("_remove_instructions_after_read")
def test_parse_uses_selected_content_when_instruction_file_disappears(
    adapter: CodexCliAdapter, instructions_file: Path
) -> None:
    extension, = adapter.parse(instructions_file)
    canonical = extension.canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert canonical.content == "Project instructions"


def test_parse_returns_nothing_when_toml_is_malformed(
    malformed_toml_adapter: CodexCliAdapter,
) -> None:
    assert not malformed_toml_adapter.parse(
        malformed_toml_adapter.codex_home / "config.toml"
    )


def test_parse_returns_nothing_when_file_is_missing(
    adapter: CodexCliAdapter, tmp_path: Path
) -> None:
    assert not adapter.parse(tmp_path / "does-not-exist.toml")


def test_parse_returns_nothing_when_config_shape_is_malformed(
    adapter: CodexCliAdapter, malformed_config_path: Path
) -> None:
    assert not adapter.parse(malformed_config_path)


def test_parse_returns_nothing_when_file_type_is_unrecognized(
    adapter: CodexCliAdapter, tmp_path: Path
) -> None:
    unknown_path = tmp_path / "notes.txt"
    unknown_path.write_text("just some notes")

    assert not adapter.parse(unknown_path)


def test_serialized_mcp_server_round_trips_through_parse_when_reparsed(
    adapter: CodexCliAdapter, tmp_path: Path, mcp_server_extension: Extension
) -> None:
    rendered = adapter.serialize(mcp_server_extension)
    config_path = tmp_path / "config.toml"
    config_path.write_text(rendered)

    reparsed = adapter.parse(config_path)

    assert len(reparsed) == 1
    assert reparsed[0].name == mcp_server_extension.name
    assert reparsed[0].canonical_config == mcp_server_extension.canonical_config


def test_serialize_returns_raw_content_when_extension_is_a_memory_file(
    adapter: CodexCliAdapter,
) -> None:
    canonical = MemoryFileConfig(content="# Hello\n", is_persistent_memory=False)
    extension = Extension(name="AGENTS.md", canonical_config=canonical)

    assert adapter.serialize(extension) == "# Hello\n"


def test_walk_up_behavior_matches_codex_contract_when_extension_type_varies(
    adapter: CodexCliAdapter,
    expected_walk_up_behavior: tuple[ExtensionType, WalkUpBehavior],
) -> None:
    extension_type, expected = expected_walk_up_behavior

    assert adapter.walk_up_behavior(extension_type) == expected


def test_capabilities_reports_supported_types_and_scopes_when_accessed(
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


def test_precedence_chain_lists_every_layer_in_precedence_order_when_project_given(
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
        (Scope.USER, str(adapter.codex_home / "AGENTS.override.md")),
        (Scope.USER, str(adapter.codex_home / "AGENTS.md")),
        (Scope.PROJECT, str(project_root / "AGENTS.override.md")),
        (Scope.PROJECT, str(project_root / "AGENTS.md")),
    ]


def test_precedence_chain_numbers_layers_consecutively_when_project_given(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    chain = global_and_project_adapter.precedence_chain(global_and_project_project_root)

    assert [layer.order_rank for layer in chain.layers] == list(range(1, 10))  # type: ignore[union-attr]


def test_precedence_chain_tags_registered_origins_when_project_root_is_given(
    global_and_project_adapter: CodexCliAdapter,
    global_and_project_project_root: Path,
) -> None:
    chain = global_and_project_adapter.precedence_chain(global_and_project_project_root)

    project_layers = [layer for layer in chain.layers if layer.scope == Scope.PROJECT]
    assert project_layers
    assert all(
        layer.origin == LayerOrigin.REGISTERED_PROJECT for layer in project_layers
    )


def test_precedence_chain_omits_project_layers_when_project_root_is_absent(
    global_and_project_adapter: CodexCliAdapter,
) -> None:
    chain = global_and_project_adapter.precedence_chain(None)

    assert Scope.PROJECT not in {layer.scope for layer in chain.layers}
    assert [layer.order_rank for layer in chain.layers] == list(range(1, 7))  # type: ignore[union-attr]


def test_command_line_argument_layer_never_resolves_when_scanned_statically(
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
def test_precedence_chain_reports_administrator_owned_config_when_present(
    adapter: CodexCliAdapter,
) -> None:
    chain = adapter.precedence_chain(None)

    managed_layers = [layer for layer in chain.layers if layer.scope == Scope.MANAGED]
    assert [layer.file_path for layer in managed_layers] == [
        str(adapter.managed_config_path),
        str(adapter.system_config_path),
    ]
    assert all(layer.exists and layer.resolves for layer in managed_layers)


def test_base_instructions_do_not_resolve_when_override_exists(
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


def test_managed_config_path_follows_platform_when_operating_system_varies(
    adapter: CodexCliAdapter, expected_managed_config_path: Path
) -> None:
    assert adapter.managed_config_path == expected_managed_config_path


def test_default_codex_home_uses_environment_path_when_variable_is_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "elsewhere"))

    assert default_codex_home() == tmp_path / "elsewhere"


def test_default_codex_home_uses_dot_codex_when_variable_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODEX_HOME", raising=False)

    assert default_codex_home() == Path.home() / ".codex"


def test_locate_project_config_stops_at_git_root_when_working_directory_is_nested(
    adapter: CodexCliAdapter, nested_project_files: NestedProjectFiles
) -> None:
    working_directory = nested_project_files.working_directory
    files = nested_project_files.files

    assert set(adapter.locate_project_config(working_directory)) == set(files)


def test_precedence_chain_lists_instructions_root_first_when_working_directory_is_nested(
    adapter: CodexCliAdapter, nested_project_files: NestedProjectFiles
) -> None:
    working_directory = nested_project_files.working_directory
    project_root = nested_project_files.root

    chain = adapter.precedence_chain(working_directory)

    assert [
        Path(layer.file_path)
        for layer in chain.layers
        if layer.scope == Scope.PROJECT and layer.exists
    ] == [
        working_directory / ".codex" / "config.toml",
        project_root / ".codex" / "config.toml",
        project_root / "AGENTS.md",
        working_directory.parent / "AGENTS.override.md",
        working_directory / "AGENTS.md",
    ]


def test_precedence_chain_tags_ancestor_layers_when_working_directory_is_nested(
    adapter: CodexCliAdapter, nested_project_files: NestedProjectFiles
) -> None:
    working_directory = nested_project_files.working_directory
    files = nested_project_files.files

    chain = adapter.precedence_chain(working_directory)

    assert {
        Path(layer.file_path): layer.origin
        for layer in chain.layers
        if layer.scope == Scope.PROJECT and layer.exists
    } == {
        files[0]: LayerOrigin.REGISTERED_PROJECT,
        files[1]: LayerOrigin.ANCESTOR_DIR,
        files[2]: LayerOrigin.REGISTERED_PROJECT,
        files[3]: LayerOrigin.ANCESTOR_DIR,
        files[4]: LayerOrigin.ANCESTOR_DIR,
    }


def test_mcp_settings_survive_round_trip_when_codex_config_declares_them(
    adapter: CodexCliAdapter, configured_mcp_servers_path: Path
) -> None:
    expected = tomllib.loads(configured_mcp_servers_path.read_text())["mcp_servers"]
    local, remote = adapter.parse(configured_mcp_servers_path)
    assert isinstance(local.canonical_config, McpServerConfig)
    assert isinstance(remote.canonical_config, McpServerConfig)
    assert local.canonical_config.enabled is False
    assert remote.canonical_config.enabled is True
    for extension in (local, remote):
        rendered = adapter.serialize(extension)
        assert (
            tomllib.loads(rendered)["mcp_servers"][extension.name]
            == expected[extension.name]
        )
        configured_mcp_servers_path.write_text(rendered)
        assert adapter.parse(configured_mcp_servers_path)[0].canonical_config == (
            extension.canonical_config
        )
