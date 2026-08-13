import json
import platform
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from agentctl.domain import (
    ConsultedLayer,
    Extension,
    ExtensionType,
    LayerOrigin,
    McpServerConfig,
    MemoryFileConfig,
    NotConsultedLayer,
    PrecedenceChain,
    PrecedenceLayer,
    Scope,
    SkillConfig,
    Source,
)
from agentctl.utils import logger

from .protocol import (
    AdapterCapabilities,
    MergeSemantics,
    WalkUpBehavior,
    WalkUpStop,
    WorkflowTargetForm,
)

_SKILL_FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)", re.DOTALL)


def slugify_project_path(project_root: Path) -> str:
    """Best-effort match of the directory naming Claude Code uses under
    `~/.claude/projects/<slug>/` for a project's auto-memory (SPECS.md §15).

    Real Claude Code derives `<slug>` from the project's git repository root
    so worktrees of the same repo share one memory directory; this adapter
    has no git awareness and slugifies `project_root` itself instead, which
    only matches for a plain (non-worktree) checkout.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", str(project_root))


def _default_managed_settings_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path("/Library/Application Support/ClaudeCode/managed-settings.json")
    if system == "Windows":
        return Path(r"C:\Program Files\ClaudeCode\managed-settings.json")
    return Path("/etc/claude-code/managed-settings.json")


def auto_memory_path(home: Path, project_root: Path) -> Path:
    """Where Claude Code stores a project's user-scoped auto-memory (SPECS.md §15)."""
    return (
        home
        / ".claude"
        / "projects"
        / slugify_project_path(project_root)
        / "memory"
        / "MEMORY.md"
    )


def _mcp_server_to_dict(config: McpServerConfig) -> dict[str, object]:
    data: dict[str, object] = {}
    if config.command:
        data["command"] = config.command
    if config.args:
        data["args"] = config.args
    if config.env:
        data["env"] = config.env
    if config.url:
        data["url"] = config.url
    if config.headers:
        data["headers"] = config.headers
    return data


class ClaudeCodeAdapter:
    """Reads Claude Code's on-disk config into canonical `Extension` records
    (ROADMAP.md PR 1.1). Read-only: `serialize` renders a canonical record
    back into Claude Code's native format for a caller to write, but this
    adapter never writes to disk itself.
    """

    source: Source = Source.CLAUDE_CODE

    def __init__(
        self,
        *,
        home: Path | None = None,
        managed_settings_path: Path | None = None,
    ) -> None:
        self._home = home if home is not None else Path.home()
        self._managed_settings_path = (
            managed_settings_path
            if managed_settings_path is not None
            else _default_managed_settings_path()
        )

    def locate_global_config(self) -> list[Path]:
        candidates = [
            self._home / ".claude.json",
            self._home / ".claude" / "settings.json",
            self._home / ".claude" / "CLAUDE.md",
        ]
        return [path for path in candidates if path.is_file()]

    def locate_project_config(self, project_root: Path) -> list[Path]:
        candidates = [
            project_root / ".claude" / "settings.json",
            project_root / ".claude" / "settings.local.json",
            project_root / "CLAUDE.md",
            project_root / ".claude" / "memory" / "MEMORY.md",
            auto_memory_path(self._home, project_root),
        ]
        paths = [path for path in candidates if path.is_file()]
        skills_directory = project_root / ".claude" / "skills"
        if skills_directory.is_dir():
            paths.extend(sorted(skills_directory.glob("*/SKILL.md")))
        return paths

    def parse(self, path: Path) -> list[Extension]:
        if not path.is_file():
            return []
        if path.name == "SKILL.md":
            return self._parse_skill(path)
        if path.name in {"CLAUDE.md", "MEMORY.md"}:
            return self._parse_memory_file(
                path, is_persistent_memory=path.name == "MEMORY.md"
            )
        if path.suffix == ".json":
            return self._parse_json_config(path)
        logger.warning(f"Claude Code adapter has no parser for {path}")
        return []

    @staticmethod
    def _parse_json_config(path: Path) -> list[Extension]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning(f"Skipping malformed JSON in {path}: {exc}")
            return []
        if not isinstance(data, dict):
            logger.warning(
                f"Skipping {path}: expected a JSON object, got {type(data).__name__}"
            )
            return []
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            return []
        extensions = []
        for name, server_config in servers.items():
            if not isinstance(server_config, dict):
                logger.warning(
                    f"Skipping malformed MCP server entry {name!r} in {path}"
                )
                continue
            try:
                canonical = McpServerConfig(
                    command=server_config.get("command"),
                    args=server_config.get("args", []),
                    env=server_config.get("env", {}),
                    url=server_config.get("url"),
                    headers=server_config.get("headers", {}),
                )
            except ValidationError as exc:
                logger.warning(
                    f"Skipping invalid MCP server entry {name!r} in {path}: {exc}"
                )
                continue
            extensions.append(
                Extension(
                    name=name,
                    origin_harness=Source.CLAUDE_CODE,
                    canonical_config=canonical,
                )
            )
        return extensions

    @staticmethod
    def _parse_memory_file(
        path: Path, *, is_persistent_memory: bool
    ) -> list[Extension]:
        content = path.read_text(encoding="utf-8")
        canonical = MemoryFileConfig(
            content=content, is_persistent_memory=is_persistent_memory
        )
        return [
            Extension(
                name=path.name,
                origin_harness=Source.CLAUDE_CODE,
                canonical_config=canonical,
            )
        ]

    @staticmethod
    def _parse_skill(path: Path) -> list[Extension]:
        text = path.read_text(encoding="utf-8")
        match = _SKILL_FRONTMATTER_PATTERN.match(text)
        if not match:
            logger.warning(f"Skipping {path}: missing YAML frontmatter")
            return []
        frontmatter_text, body = match.groups()
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            logger.warning(f"Skipping {path}: invalid frontmatter YAML: {exc}")
            return []
        if not isinstance(frontmatter, dict):
            logger.warning(f"Skipping {path}: frontmatter is not a mapping")
            return []
        name = frontmatter.get("name", path.parent.name)
        bundled_files = sorted(
            str(sibling.relative_to(path.parent))
            for sibling in path.parent.rglob("*")
            if sibling.is_file() and sibling != path
        )
        try:
            canonical = SkillConfig(
                description=frontmatter.get("description", ""),
                body=body.strip(),
                bundled_files=bundled_files,
            )
        except ValidationError as exc:
            logger.warning(f"Skipping {path}: invalid skill shape: {exc}")
            return []
        return [
            Extension(
                name=name, origin_harness=Source.CLAUDE_CODE, canonical_config=canonical
            )
        ]

    @staticmethod
    def serialize(extension: Extension) -> str:
        config = extension.canonical_config
        if isinstance(config, McpServerConfig):
            payload = {"mcpServers": {extension.name: _mcp_server_to_dict(config)}}
            return json.dumps(payload, indent=2)
        if isinstance(config, MemoryFileConfig):
            return config.content
        if isinstance(config, SkillConfig):
            frontmatter = yaml.safe_dump(
                {"name": extension.name, "description": config.description},
                sort_keys=False,
            ).strip()
            return f"---\n{frontmatter}\n---\n\n{config.body}\n"
        raise TypeError(f"Unsupported canonical config type: {type(config)!r}")

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

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        user_settings_path = self._home / ".claude" / "settings.json"
        layers: list[PrecedenceLayer] = [
            ConsultedLayer(
                scope=Scope.MANAGED,
                file_path=str(self._managed_settings_path),
                exists=self._managed_settings_path.is_file(),
                origin=LayerOrigin.GLOBAL,
                order_rank=1,
                resolves=self._managed_settings_path.is_file(),
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
        if project_root is not None:
            local_settings_path = project_root / ".claude" / "settings.local.json"
            project_settings_path = project_root / ".claude" / "settings.json"
            layers.append(
                ConsultedLayer(
                    scope=Scope.LOCAL,
                    file_path=str(local_settings_path),
                    exists=local_settings_path.is_file(),
                    origin=LayerOrigin.REGISTERED_PROJECT,
                    order_rank=3,
                    resolves=local_settings_path.is_file(),
                )
            )
            layers.append(
                ConsultedLayer(
                    scope=Scope.PROJECT,
                    file_path=str(project_settings_path),
                    exists=project_settings_path.is_file(),
                    origin=LayerOrigin.REGISTERED_PROJECT,
                    order_rank=4,
                    resolves=project_settings_path.is_file(),
                )
            )
        layers.append(
            ConsultedLayer(
                scope=Scope.USER,
                file_path=str(user_settings_path),
                exists=user_settings_path.is_file(),
                origin=LayerOrigin.GLOBAL,
                order_rank=5,
                resolves=user_settings_path.is_file(),
            )
        )

        # Verified against current Claude Code docs (code.claude.com/docs/en/memory,
        # "AGENTS.md" section, fetched 2026-08-13): "Claude Code reads CLAUDE.md,
        # not AGENTS.md." Confirmed not_consulted, not unconfirmed (SPECS.md §5.1).
        agents_md_path = (
            (project_root / "AGENTS.md")
            if project_root is not None
            else (self._home / "AGENTS.md")
        )
        layers.append(
            NotConsultedLayer(
                scope=Scope.GLOBAL,
                file_path=str(agents_md_path),
                exists=agents_md_path.is_file(),
                origin=(
                    LayerOrigin.REGISTERED_PROJECT
                    if project_root is not None
                    else LayerOrigin.GLOBAL
                ),
            )
        )
        return PrecedenceChain(source=self.source, project_id=None, layers=layers)

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
