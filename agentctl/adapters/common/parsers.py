import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import tomlkit
import yaml
from pydantic import ValidationError
from tomlkit.exceptions import TOMLKitError

from agentctl.domain import (
    Extension,
    McpServerConfig,
    MemoryFileConfig,
    SkillConfig,
    Source,
)
from agentctl.utils import logger

SKILL_FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)", re.DOTALL)

McpServerBuilder = Callable[[Mapping[str, Any]], McpServerConfig]


def _mcp_server_extensions(
    servers: Any, *, path: Path, source: Source, build: McpServerBuilder
) -> list[Extension]:
    """Turn a source's `name -> server entry` mapping into canonical Extensions.

    Every source spells its MCP entries differently, so `build` owns the
    per-source key names; the entry-shape validation and the "one bad entry
    never sinks the file" contract are shared.
    """
    if not isinstance(servers, dict):
        return []
    extensions = []
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            logger.warning(f"Skipping malformed MCP server entry {name!r} in {path}")
            continue
        try:
            canonical = build(entry)
        except ValidationError as exc:
            logger.warning(
                f"Skipping invalid MCP server entry {name!r} in {path}: {exc}"
            )
            continue
        extensions.append(
            Extension(name=name, origin_harness=source, canonical_config=canonical)
        )
    return extensions


def _json_mcp_server(entry: Mapping[str, Any]) -> McpServerConfig:
    return McpServerConfig(
        command=entry.get("command"),
        args=entry.get("args", []),
        env=entry.get("env", {}),
        url=entry.get("url"),
        headers=entry.get("headers", {}),
    )


def _toml_mcp_server(entry: Mapping[str, Any]) -> McpServerConfig:
    # Codex names its remote-transport headers `http_headers`; everything else
    # matches the canonical field names.
    return McpServerConfig(
        command=entry.get("command"),
        args=entry.get("args", []),
        env=entry.get("env", {}),
        url=entry.get("url"),
        headers=entry.get("http_headers", {}),
    )


def parse_mcp_servers_json(path: Path, *, source: Source) -> list[Extension]:
    """Parse the `mcpServers` object shared by Claude Code and Cursor JSON config."""
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
    return _mcp_server_extensions(
        data.get("mcpServers"), path=path, source=source, build=_json_mcp_server
    )


def parse_mcp_servers_toml(path: Path, *, source: Source) -> list[Extension]:
    """Parse the `[mcp_servers.*]` tables Codex CLI keeps in `config.toml`.

    Reading is non-destructive: the document is parsed with comments and
    formatting intact and never written back, so anything the canonical shape
    has no room for — comments, unrelated tables, Codex-only keys such as
    `startup_timeout_sec` — stays exactly as the user left it on disk.
    """
    try:
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
    except TOMLKitError as exc:
        logger.warning(f"Skipping malformed TOML in {path}: {exc}")
        return []
    return _mcp_server_extensions(
        document.unwrap().get("mcp_servers"),
        path=path,
        source=source,
        build=_toml_mcp_server,
    )


def parse_memory_file(
    path: Path, *, source: Source, is_persistent_memory: bool
) -> list[Extension]:
    """Parse a whole markdown memory/instruction file (CLAUDE.md, AGENTS.md, …)."""
    canonical = MemoryFileConfig(
        content=path.read_text(encoding="utf-8"),
        is_persistent_memory=is_persistent_memory,
    )
    return [
        Extension(name=path.name, origin_harness=source, canonical_config=canonical)
    ]


def parse_skill(path: Path, *, source: Source) -> list[Extension]:
    """Parse a SKILL.md-style skill: YAML frontmatter, body, and bundled siblings."""
    text = path.read_text(encoding="utf-8")
    match = SKILL_FRONTMATTER_PATTERN.match(text)
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
    return [Extension(name=name, origin_harness=source, canonical_config=canonical)]
