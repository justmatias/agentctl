import json
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from agentctl.domain import (
    Extension,
    McpServerConfig,
    MemoryFileConfig,
    SkillConfig,
    Source,
)
from agentctl.utils import logger

SKILL_FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)", re.DOTALL)


def parse_json_config(path: Path) -> list[Extension]:
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
            logger.warning(f"Skipping malformed MCP server entry {name!r} in {path}")
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


def parse_memory_file(path: Path, *, is_persistent_memory: bool) -> list[Extension]:
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


def parse_skill(path: Path) -> list[Extension]:
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
    return [
        Extension(
            name=name, origin_harness=Source.CLAUDE_CODE, canonical_config=canonical
        )
    ]
