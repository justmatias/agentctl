"""Pydantic domain models for the Phase-0 subset of SPECS.md §8."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from .canonical_configs import (
    CanonicalConfig,
    McpServerConfig,
    MemoryFileConfig,
    SkillConfig,
)
from .enums import (
    ConflictResolution,
    ExtensionType,
    LayerOrigin,
    LayerStatus,
    Scope,
    Source,
    SyncState,
)

_CANONICAL_CONFIG_TYPES: dict[ExtensionType, type[CanonicalConfig]] = {
    ExtensionType.MCP_SERVER: McpServerConfig,
    ExtensionType.MEMORY_FILE: MemoryFileConfig,
    ExtensionType.SKILL: SkillConfig,
}


class Extension(BaseModel):
    """A managed config object, normalized independent of harness format."""

    id: UUID = Field(default_factory=uuid4)
    type: ExtensionType
    name: str
    origin_harness: Source | None = None
    canonical_config: CanonicalConfig
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate_canonical_config_matches_type(self) -> "Extension":
        expected = _CANONICAL_CONFIG_TYPES[self.type]
        if not isinstance(self.canonical_config, expected):
            # ValueError (not TypeError) is required: pydantic only wraps
            # ValueError/AssertionError from validators into ValidationError.
            raise ValueError(  # noqa: TRY004
                f"canonical_config must be {expected.__name__} for type "
                f"{self.type.value!r}, got {type(self.canonical_config).__name__}"
            )
        return self


class Binding(BaseModel):
    """The projection of a canonical Extension into a specific harness's file(s)."""

    id: UUID = Field(default_factory=uuid4)
    extension_id: UUID
    harness: Source
    scope: Scope
    file_path: str
    enabled: bool = True
    sync_state: SyncState = SyncState.IN_SYNC
    last_written_hash: str | None = None
    last_seen_hash: str | None = None


class Conflict(BaseModel):
    """Structured config only (SPECS §7.2): the same extension defined differently."""

    id: UUID = Field(default_factory=uuid4)
    extension_id: UUID
    binding_ids: list[UUID]
    resolved_binding_id: UUID | None = None
    resolution: ConflictResolution = ConflictResolution.UNRESOLVED

    @model_validator(mode="after")
    def _validate_resolution_consistency(self) -> "Conflict":
        if (
            self.resolution == ConflictResolution.SOURCE_CHOSEN
            and self.resolved_binding_id is None
        ):
            raise ValueError(
                "resolved_binding_id is required when resolution is source_chosen"
            )
        if (
            self.resolution != ConflictResolution.SOURCE_CHOSEN
            and self.resolved_binding_id is not None
        ):
            raise ValueError(
                "resolved_binding_id must be unset unless resolution is source_chosen"
            )
        return self


class Project(BaseModel):
    """A directory the user has explicitly registered with the tool (SPECS §7.9)."""

    id: UUID = Field(default_factory=uuid4)
    path: Path
    display_name: str
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detected_sources: list[Source] = []

    @field_validator("path")
    @classmethod
    def _validate_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("Project.path must be absolute")
        return value


class PrecedenceLayer(BaseModel):
    """One layer of a PrecedenceChain (SPECS §7.10)."""

    scope: Scope
    file_path: str
    exists: bool
    order_rank: int | None = None
    status: LayerStatus
    origin: LayerOrigin
    resolves: bool

    @model_validator(mode="after")
    def _validate_status_rules(self) -> "PrecedenceLayer":
        if self.status == LayerStatus.CONSULTED:
            if self.order_rank is None:
                raise ValueError("consulted layers must have an order_rank")
        else:
            if self.order_rank is not None:
                raise ValueError(
                    "only consulted layers may carry an order_rank "
                    f"(status={self.status.value!r})"
                )
            if self.resolves:
                raise ValueError(
                    f"layers with status={self.status.value!r} must not resolve"
                )
        return self


class PrecedenceChain(BaseModel):
    """The full ordered stack of sources that could define config for a key."""

    source: Source
    project_id: UUID | None = None
    layers: list[PrecedenceLayer] = []
