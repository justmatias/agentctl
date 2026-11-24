import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import ClassVar

from pydantic import AliasChoices, AliasPath, BaseModel, Field, ValidationError

from agentctl.adapters.common import (
    consulted_file_layer,
    dispatch_serializer,
    parse_mcp_servers_json,
    parse_memory_file,
    parse_skill,
    platform_specific_path,
)
from agentctl.adapters.protocol import (
    AdapterCapabilities,
    MergeSemantics,
    ScopedConfigPath,
    WalkUpBehavior,
    WalkUpStop,
    WorkflowTargetForm,
)
from agentctl.domain import (
    ConsultedLayer,
    Extension,
    ExtensionType,
    LayerOrigin,
    NotConsultedLayer,
    PrecedenceChain,
    PrecedenceLayer,
    Scope,
    Source,
    UnconfirmedLayer,
)
from agentctl.utils import logger

from .serializers import SERIALIZERS

AGENTS_MD_PLUGIN_IDS = ("cc-plugin-agents-md@builtin", "agents-md@builtin")


class InstructionFilesSetting(BaseModel):
    """The `instructionFiles` option of Claude's built-in AGENTS.md plugin.

    Older Claude Code versions use the second plugin ID; newer ones read either.
    https://code.claude.com/docs/en/memory#when-claude-code-reads-agents-md
    """

    value: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            *(
                AliasPath("pluginConfigs", plugin_id, "options", "instructionFiles")
                for plugin_id in AGENTS_MD_PLUGIN_IDS
            )
        ),
    )


class AutoMemorySetting(BaseModel):
    enabled: bool | None = Field(default=None, validation_alias="autoMemoryEnabled")


class AgentsMdPluginSetting(BaseModel):
    enabled: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            *(AliasPath("enabledPlugins", plugin_id) for plugin_id in AGENTS_MD_PLUGIN_IDS)
        ),
    )


def default_managed_settings_path() -> Path:
    return platform_specific_path(
        darwin=Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
        windows=Path(r"C:\Program Files\ClaudeCode\managed-settings.json"),
        default=Path("/etc/claude-code/managed-settings.json"),
    )


@dataclass(kw_only=True)
class ClaudeCodeAdapter:
    """Reads Claude Code's on-disk config into canonical `Extension` records"""

    source: ClassVar[Source] = Source.CLAUDE_CODE
    home: Path = field(default_factory=Path.home)
    managed_settings_path: Path = field(default_factory=default_managed_settings_path)

    @property
    def user_settings_path(self) -> Path:
        return self.home / ".claude" / "settings.json"

    @staticmethod
    def project_settings_path(project_root: Path) -> Path:
        return project_root / ".claude" / "settings.json"

    @staticmethod
    def local_settings_path(project_root: Path) -> Path:
        return project_root / ".claude" / "settings.local.json"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            source=Source.CLAUDE_CODE,
            extension_types=frozenset({
                ExtensionType.MCP_SERVER,
                ExtensionType.MEMORY_FILE,
                ExtensionType.SKILL,
            }),
            scopes=frozenset({
                Scope.MANAGED,
                Scope.LOCAL,
                Scope.PROJECT,
                Scope.USER,
                Scope.GLOBAL,
            }),
            workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
        )

    def auto_memory_path(self, project_root: Path) -> Path:
        """Where Claude Code stores a project's user-scoped auto-memory (SPECS.md §15)."""
        # Real Claude Code derives the `<slug>` directory name from the project's
        # git repository root so worktrees of the same repo share one memory
        # directory; this adapter has no git awareness and slugifies
        # `project_root` itself instead, which only matches for a plain
        # (non-worktree) checkout.
        slug = re.sub(r"[^A-Za-z0-9]", "-", str(project_root))
        return self.home / ".claude" / "projects" / slug / "memory" / "MEMORY.md"

    @staticmethod
    def _read_settings[Settings: BaseModel](
        path: Path, model: type[Settings]
    ) -> Settings | None:
        try:
            if not path.is_file():
                return None
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError, ValidationError) as error:
            logger.warning(f"Skipping unreadable settings in {path}: {type(error).__name__}")
            return None

    @property
    def instruction_files_setting(self) -> str | None:
        """The `instructionFiles` option, which Claude reads only from managed
        and user settings, managed first."""
        for path in (self.managed_settings_path, self.user_settings_path):
            setting = self._read_settings(path, InstructionFilesSetting)
            if setting is not None and setting.value is not None:
                return setting.value
        return None

    def locate_scoped_global_config(self) -> list[ScopedConfigPath]:
        paths = [ScopedConfigPath(path, Scope.USER) for path in self.locate_global_config()]
        paths.extend(
            ScopedConfigPath(path, Scope.USER)
            for path in (self.home / ".claude" / "skills").glob("*/SKILL.md")
            if path.is_file()
        )
        managed_mcp_path = self.managed_settings_path.with_name("managed-mcp.json")
        if managed_mcp_path.is_file():
            paths.append(ScopedConfigPath(managed_mcp_path, Scope.MANAGED))
        return paths

    def locate_global_config(self) -> list[Path]:
        candidates = [
            self.home / ".claude.json",
            self.user_settings_path,
            self.home / ".claude" / "CLAUDE.md",
        ]
        return [path for path in candidates if path.is_file()]

    def locate_project_config(self, project_root: Path) -> list[Path]:
        candidates = [
            self.project_settings_path(project_root),
            self.local_settings_path(project_root),
            project_root / "CLAUDE.md",
            project_root / ".claude" / "memory" / "MEMORY.md",
            self.auto_memory_path(project_root),
        ]
        paths = [path for path in candidates if path.is_file()]
        skills_directory = project_root / ".claude" / "skills"
        if skills_directory.is_dir():
            paths.extend(sorted(skills_directory.glob("*/SKILL.md")))
        return paths

    def parse(self, path: Path, *, scope: Scope | None = None) -> list[Extension]:
        del scope
        if not path.is_file():
            return []
        if path.name == "SKILL.md":
            return parse_skill(path, source=self.source)
        if path.name in {"CLAUDE.md", "MEMORY.md"}:
            return parse_memory_file(
                path,
                source=self.source,
                is_persistent_memory=path.name == "MEMORY.md",
            )
        if path.suffix == ".json":
            return parse_mcp_servers_json(path, source=self.source)
        logger.warning(f"Claude Code adapter has no parser for {path}")
        return []

    def serialize(self, extension: Extension) -> str:  # pylint: disable=no-self-use
        return dispatch_serializer(SERIALIZERS, extension)

    @staticmethod
    def walk_up_behavior(extension_type: ExtensionType) -> WalkUpBehavior:
        if extension_type == ExtensionType.MEMORY_FILE:
            return WalkUpBehavior(
                ascends=True,
                stops_at=WalkUpStop.FILESYSTEM_ROOT,
                merge_semantics=MergeSemantics.CONCATENATE,
            )
        return WalkUpBehavior(
            ascends=False,
            stops_at=WalkUpStop.NONE,
            merge_semantics=MergeSemantics.OVERRIDE,
        )

    @property
    def agents_md_plugin_enabled(self) -> bool:
        for path in (self.managed_settings_path, self.user_settings_path):
            setting = self._read_settings(path, AgentsMdPluginSetting)
            if setting is not None and setting.enabled is not None:
                return setting.enabled
        return True

    def _project_agents_md_layer(
        self, project_root: Path, ranks: Iterator[int]
    ) -> PrecedenceLayer:
        """The project AGENTS.md layer, as the `instructionFiles` setting decides."""
        path = project_root / "AGENTS.md"
        setting = (
            self.instruction_files_setting if self.agents_md_plugin_enabled else "claude-md"
        )
        if setting == "claude-md-and-agents-md":
            return consulted_file_layer(
                scope=Scope.PROJECT,
                path=path,
                origin=LayerOrigin.REGISTERED_PROJECT,
                order_rank=next(ranks),
            )
        layer_type = NotConsultedLayer if setting == "claude-md" else UnconfirmedLayer
        # The default loads AGENTS.md only when no CLAUDE.md exists, and its
        # support depends on the Claude version, so it stays unconfirmed.
        return layer_type(
            scope=Scope.PROJECT,
            file_path=str(path),
            exists=path.is_file(),
            origin=LayerOrigin.REGISTERED_PROJECT,
        )

    def auto_memory_enabled(self, project_root: Path) -> bool:
        for path in (
            self.managed_settings_path,
            self.local_settings_path(project_root),
            self.project_settings_path(project_root),
            self.user_settings_path,
        ):
            setting = self._read_settings(path, AutoMemorySetting)
            if setting is not None and setting.enabled is not None:
                return setting.enabled
        return True

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        layers: list[PrecedenceLayer] = [
            consulted_file_layer(
                scope=Scope.MANAGED,
                path=self.managed_settings_path,
                origin=LayerOrigin.GLOBAL,
                order_rank=1,
            ),
            # Command-line arguments rank above every file-backed layer but are
            # never persisted on disk, so they can never resolve from a static
            # scan. Scope.GLOBAL is reused here as the only Scope value not
            # already claimed by one of Claude Code's four file-backed scopes.
            ConsultedLayer(
                scope=Scope.GLOBAL,
                file_path="(command-line arguments)",
                exists=False,
                origin=LayerOrigin.GLOBAL,
                order_rank=2,
                resolves=False,
            ),
        ]

        if project_root:
            layers.extend(
                [
                    consulted_file_layer(
                        scope=Scope.LOCAL,
                        path=self.local_settings_path(project_root),
                        origin=LayerOrigin.REGISTERED_PROJECT,
                        order_rank=3,
                    ),
                    consulted_file_layer(
                        scope=Scope.PROJECT,
                        path=self.project_settings_path(project_root),
                        origin=LayerOrigin.REGISTERED_PROJECT,
                        order_rank=4,
                    ),
                ]
            )

        layers.append(
            consulted_file_layer(
                scope=Scope.USER,
                path=self.user_settings_path,
                origin=LayerOrigin.GLOBAL,
                order_rank=5,
            )
        )

        # https://code.claude.com/docs/en/memory#choose-where-to-put-claude-md-files
        ranks = count(6)
        if project_root is not None:
            layers.extend(
                consulted_file_layer(
                    scope=Scope.PROJECT,
                    path=project_root / filename,
                    origin=LayerOrigin.REGISTERED_PROJECT,
                    order_rank=next(ranks),
                )
                for filename in ("CLAUDE.local.md", ".claude/CLAUDE.md", "CLAUDE.md")
            )
            # A directory's AGENTS.md loads right after its CLAUDE.md files.
            layers.append(self._project_agents_md_layer(project_root, ranks))
        layers.append(
            consulted_file_layer(
                scope=Scope.USER,
                path=self.home / ".claude" / "CLAUDE.md",
                origin=LayerOrigin.GLOBAL,
                order_rank=next(ranks),
            )
        )
        if project_root is not None:
            memory_path = self.auto_memory_path(project_root)
            if self.auto_memory_enabled(project_root):
                layers.append(
                    consulted_file_layer(
                        scope=Scope.USER,
                        path=memory_path,
                        origin=LayerOrigin.REGISTERED_PROJECT,
                        order_rank=next(ranks),
                    )
                )
            else:
                layers.append(
                    NotConsultedLayer(
                        scope=Scope.USER,
                        file_path=str(memory_path),
                        exists=memory_path.is_file(),
                        origin=LayerOrigin.REGISTERED_PROJECT,
                    )
                )
        else:
            agents_path = self.home / "AGENTS.md"
            layers.append(
                NotConsultedLayer(
                    scope=Scope.GLOBAL,
                    file_path=str(agents_path),
                    exists=agents_path.is_file(),
                    origin=LayerOrigin.GLOBAL,
                )
            )
        return PrecedenceChain(source=self.source, project_id=None, layers=layers)
