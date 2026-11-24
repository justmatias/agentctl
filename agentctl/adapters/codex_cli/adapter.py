import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import ClassVar, Literal

from agentctl.adapters.common import (
    consulted_file_layer,
    dispatch_serializer,
    parse_mcp_servers_toml,
    platform_specific_path,
    project_directories,
)
from agentctl.adapters.protocol import (
    AdapterCapabilities,
    MergeSemantics,
    WalkUpBehavior,
    WalkUpStop,
    WorkflowTargetForm,
)
from agentctl.domain import (
    ConsultedLayer,
    Extension,
    ExtensionType,
    LayerOrigin,
    MemoryFileConfig,
    PrecedenceChain,
    PrecedenceLayer,
    Scope,
    Source,
)
from agentctl.utils import logger

from .serializers import SERIALIZERS

CODEX_HOME_VARIABLE = "CODEX_HOME"
SYSTEM_CONFIG_DIRECTORY = Path("/etc/codex")
CONFIG_FILENAME = "config.toml"
MANAGED_CONFIG_FILENAME = "managed_config.toml"
INSTRUCTIONS_FILENAME = "AGENTS.md"
INSTRUCTIONS_OVERRIDE_FILENAME = "AGENTS.override.md"
COMMAND_LINE_ARGUMENTS = "(command-line arguments)"


def default_codex_home() -> Path:
    """Codex's home directory: `~/.codex` unless `CODEX_HOME` overrides it."""
    override = os.environ.get(CODEX_HOME_VARIABLE)
    return Path(override) if override else Path.home() / ".codex"


@dataclass(kw_only=True)
class CodexCliAdapter:
    """Reads Codex CLI's on-disk config into canonical `Extension` records"""

    source: ClassVar[Source] = Source.CODEX_CLI
    codex_home: Path = field(default_factory=default_codex_home)
    # Codex reads machine-wide config from /etc/codex on Unix only; on Windows
    # the layer simply never exists, so the Unix path is still what we report.
    system_config_directory: Path = SYSTEM_CONFIG_DIRECTORY

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            source=Source.CODEX_CLI,
            extension_types=frozenset({
                ExtensionType.MCP_SERVER,
                ExtensionType.MEMORY_FILE,
            }),
            # Codex has no gitignored per-project layer of its own, so nothing
            # maps to Scope.LOCAL.
            scopes=frozenset({
                Scope.MANAGED,
                Scope.PROJECT,
                Scope.USER,
                Scope.GLOBAL,
            }),
            # Codex scans `.agents/skills` (developers.openai.com/codex/skills,
            # fetched 2026-08-14), so a workflow can compile down to a skill for
            # it — but those files belong to the shared `.agents` source, which
            # is its own adapter, not to this one.
            workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
        )

    @property
    def user_config_path(self) -> Path:
        return self.codex_home / CONFIG_FILENAME

    @property
    def system_config_path(self) -> Path:
        return self.system_config_directory / CONFIG_FILENAME

    @property
    def managed_config_path(self) -> Path:
        """Where an administrator's managed config lives on this platform."""
        return platform_specific_path(
            darwin=self.system_config_directory / MANAGED_CONFIG_FILENAME,
            windows=self.codex_home / MANAGED_CONFIG_FILENAME,
            default=self.system_config_directory / MANAGED_CONFIG_FILENAME,
        )

    @staticmethod
    def project_config_path(project_root: Path) -> Path:
        return project_root / ".codex" / CONFIG_FILENAME

    @staticmethod
    def _select_instructions(
        directory: Path, *, scope: Scope
    ) -> tuple[Path, str] | None:
        for filename in (INSTRUCTIONS_OVERRIDE_FILENAME, INSTRUCTIONS_FILENAME):
            path = directory / filename
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                if content.strip():
                    return path, content
            except OSError as error:
                logger.warning(
                    f"Could not read Codex instructions from {path}: {error}"
                )
            # Project discovery picks the first file before checking its content.
            if scope == Scope.PROJECT:
                break
        return None

    def locate_global_config(self) -> list[Path]:
        candidates = [
            self.managed_config_path,
            self.system_config_path,
            self.user_config_path,
        ]
        paths = [path for path in candidates if path.is_file()]
        selected = self._select_instructions(self.codex_home, scope=Scope.USER)
        if selected is not None:
            paths.append(selected[0])
        return paths

    def locate_project_config(self, project_root: Path) -> list[Path]:
        paths = []
        for directory in project_directories(project_root):
            config_path = self.project_config_path(directory)
            if config_path.is_file():
                paths.append(config_path)
            selected = self._select_instructions(directory, scope=Scope.PROJECT)
            if selected is not None:
                paths.append(selected[0])
        return paths

    def parse(
        self, path: Path, *, scope: Literal[Scope.USER, Scope.PROJECT] | None = None
    ) -> list[Extension]:
        """Parse a file using its instruction scope if supplied.

        Paths in Codex home default to user scope. Pass project scope when
        parsing that directory as part of a project.
        """
        if not path.is_file():
            return []
        if path.name in {INSTRUCTIONS_FILENAME, INSTRUCTIONS_OVERRIDE_FILENAME}:
            if scope is None:
                scope = (
                    Scope.USER
                    if path.parent.resolve() == self.codex_home.resolve()
                    else Scope.PROJECT
                )
            selected = self._select_instructions(path.parent, scope=scope)
            if selected is None or selected[0] != path:
                return []
            return [
                Extension(
                    name=path.name,
                    origin_harness=self.source,
                    canonical_config=MemoryFileConfig(
                        content=selected[1], is_persistent_memory=False
                    ),
                )
            ]
        if path.suffix == ".toml":
            return parse_mcp_servers_toml(path, source=self.source)
        logger.warning(f"Codex CLI adapter has no parser for {path}")
        return []

    def serialize(self, extension: Extension) -> str:  # pylint: disable=no-self-use
        return dispatch_serializer(SERIALIZERS, extension)

    @staticmethod
    def walk_up_behavior(extension_type: ExtensionType) -> WalkUpBehavior:
        """Codex consults every directory between the project root and the
        working directory, for both `.codex/config.toml` and `AGENTS.md`
        (learn.chatgpt.com/docs/config-file/config-basic and
        .../agent-configuration/agents-md, fetched 2026-08-14). Config keys are
        overridden by the closest directory; instructions are concatenated.
        """
        return WalkUpBehavior(
            ascends=True,
            stops_at=WalkUpStop.GIT_ROOT,
            merge_semantics=(
                MergeSemantics.CONCATENATE
                if extension_type == ExtensionType.MEMORY_FILE
                else MergeSemantics.OVERRIDE
            ),
        )

    def _build_directory_instructions_layers(
        self,
        directory: Path,
        *,
        scope: Scope,
        origin: LayerOrigin,
        ranks: Iterator[int],
    ) -> list[PrecedenceLayer]:
        """The `AGENTS.override.md` / `AGENTS.md` pair one directory contributes.

        Only the selected file can resolve. Keep both candidates in the
        inventory so an existing file that was skipped is still visible.
        """
        override_path = directory / INSTRUCTIONS_OVERRIDE_FILENAME
        base_path = directory / INSTRUCTIONS_FILENAME
        selected = self._select_instructions(directory, scope=scope)
        layers: list[PrecedenceLayer] = []
        for path in (override_path, base_path):
            exists = path.is_file()
            resolves = exists and selected is not None and path == selected[0]
            layers.append(
                ConsultedLayer(
                    scope=scope,
                    file_path=str(path),
                    exists=exists,
                    origin=origin,
                    order_rank=next(ranks),
                    resolves=resolves,
                )
            )
        return layers

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        """Report config and instruction candidates in one ordered inventory.

        Config ranks run from highest to lowest override priority. The
        instruction ranks that follow describe concatenation order: Codex home
        first, then project root through working directory. Only the candidate
        marked as resolving in each directory contributes instructions.

        Config precedence is quoted from
        learn.chatgpt.com/docs/config-file/config-basic (fetched 2026-08-14);
        managed config outranking CLI overrides is from
        learn.chatgpt.com/docs/enterprise/managed-configuration. The profile
        layer (`~/.codex/<name>.config.toml`, selected at runtime with
        `--profile`) sits between the project and user layers and is not
        reported yet — no static scan can tell which profile is in play.
        """
        ranks = count(1)
        layers: list[PrecedenceLayer] = [
            consulted_file_layer(
                scope=Scope.MANAGED,
                path=self.managed_config_path,
                origin=LayerOrigin.GLOBAL,
                order_rank=next(ranks),
            ),
            # `-c`/`--config` overrides outrank every file except the managed
            # one, but never touch disk, so they can never resolve from a
            # static scan. Scope.GLOBAL stands in for "not a file scope", as it
            # does in the Claude Code adapter.
            ConsultedLayer(
                scope=Scope.GLOBAL,
                file_path=COMMAND_LINE_ARGUMENTS,
                exists=False,
                origin=LayerOrigin.GLOBAL,
                order_rank=next(ranks),
                resolves=False,
            ),
        ]
        directories = project_directories(project_root) if project_root is not None else ()
        directory_origins = [
            (directory, LayerOrigin.ANCESTOR_DIR if index else LayerOrigin.REGISTERED_PROJECT)
            for index, directory in enumerate(directories)
        ]
        for directory, origin in directory_origins:
            layers.append(
                consulted_file_layer(
                    scope=Scope.PROJECT,
                    path=self.project_config_path(directory),
                    origin=origin,
                    order_rank=next(ranks),
                )
            )
        layers.extend(
            [
                consulted_file_layer(
                    scope=Scope.USER,
                    path=self.user_config_path,
                    origin=LayerOrigin.GLOBAL,
                    order_rank=next(ranks),
                ),
                consulted_file_layer(
                    scope=Scope.MANAGED,
                    path=self.system_config_path,
                    origin=LayerOrigin.GLOBAL,
                    order_rank=next(ranks),
                ),
            ]
        )
        layers.extend(
            self._build_directory_instructions_layers(
                self.codex_home,
                scope=Scope.USER,
                origin=LayerOrigin.GLOBAL,
                ranks=ranks,
            )
        )
        for directory, origin in reversed(directory_origins):
            layers.extend(
                self._build_directory_instructions_layers(
                    directory,
                    scope=Scope.PROJECT,
                    origin=origin,
                    ranks=ranks,
                )
            )
        return PrecedenceChain(source=self.source, project_id=None, layers=layers)
