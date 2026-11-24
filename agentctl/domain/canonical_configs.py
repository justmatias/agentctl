from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import ExtensionType


class CodexMcpEnvironmentVariable(BaseModel):
    name: str
    source: Literal["local", "remote"] | None = None


class CodexMcpOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bearer_token_env_var: str | None = None
    env_http_headers: dict[str, str] | None = None
    env_vars: list[str | CodexMcpEnvironmentVariable] | None = None
    cwd: str | None = None
    startup_timeout_sec: float | None = None


class McpServerConfig(BaseModel):
    """Canonical shape for an MCP server, covering stdio and remote transports."""

    model_config = ConfigDict(extra="forbid")

    type: Literal[ExtensionType.MCP_SERVER] = ExtensionType.MCP_SERVER
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    url: str | None = None
    headers: dict[str, str] = {}
    enabled: bool = True
    codex: CodexMcpOptions | None = None

    @model_validator(mode="after")
    def _require_command_or_url(self) -> "McpServerConfig":
        if not self.command and not self.url:
            raise ValueError("McpServerConfig requires either 'command' or 'url'")
        return self


class MemoryFileConfig(BaseModel):
    """Canonical shape for a memory/instruction file"""

    model_config = ConfigDict(extra="forbid")

    type: Literal[ExtensionType.MEMORY_FILE] = ExtensionType.MEMORY_FILE
    content: str
    is_persistent_memory: bool = Field(
        description="True for agent-accumulated memory eg. MEMORY.MD"
    )


class SkillConfig(BaseModel):
    """Canonical shape for a SKILL.md-style skill"""

    model_config = ConfigDict(extra="forbid")

    type: Literal[ExtensionType.SKILL] = ExtensionType.SKILL
    description: str
    body: str
    bundled_files: list[str] = []


CanonicalConfig = Annotated[
    McpServerConfig | MemoryFileConfig | SkillConfig,
    Field(discriminator="type"),
]
