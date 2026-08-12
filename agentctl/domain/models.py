from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from .canonical_configs import CanonicalConfig
from .enums import (
    ConflictResolution,
    ExtensionType,
    LayerOrigin,
    LayerStatus,
    Scope,
    Source,
    SyncState,
)


class Extension(BaseModel):
    """A managed config object, normalized independent of harness format."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    origin_harness: Source | None = None
    canonical_config: CanonicalConfig
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def type(self) -> ExtensionType:
        return self.canonical_config.type


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
    """Structured config only: the same extension defined differently."""

    id: UUID = Field(default_factory=uuid4)
    extension_id: UUID
    binding_ids: list[UUID]
    resolved_binding_id: UUID | None = None
    resolution: ConflictResolution = ConflictResolution.UNRESOLVED

    @model_validator(mode="after")
    def _validate_resolution_consistency(self) -> "Conflict":
        is_source_chosen = self.resolution == ConflictResolution.SOURCE_CHOSEN
        if is_source_chosen == bool(self.resolved_binding_id):
            return self
        raise ValueError(
            "resolved_binding_id is required when resolution is source_chosen"
            if is_source_chosen
            else "resolved_binding_id must be unset unless resolution is source_chosen"
        )


class Project(BaseModel):
    """A directory the user has explicitly registered with the tool."""

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


class _PrecedenceLayerBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Scope
    file_path: str
    exists: bool
    origin: LayerOrigin


class ConsultedLayer(_PrecedenceLayerBase):
    """A layer an adapter has verified is consulted, ranked in precedence order."""

    status: Literal[LayerStatus.CONSULTED] = LayerStatus.CONSULTED
    order_rank: int
    resolves: bool


class NotConsultedLayer(_PrecedenceLayerBase):
    """A layer an adapter has verified is not consulted."""

    status: Literal[LayerStatus.NOT_CONSULTED] = LayerStatus.NOT_CONSULTED
    resolves: Literal[False] = False


class UnconfirmedLayer(_PrecedenceLayerBase):
    """A layer whose consultation could not be confirmed; it never resolves."""

    status: Literal[LayerStatus.UNCONFIRMED] = LayerStatus.UNCONFIRMED
    resolves: Literal[False] = False


PrecedenceLayer = Annotated[
    ConsultedLayer | NotConsultedLayer | UnconfirmedLayer,
    Field(discriminator="status"),
]


class PrecedenceChain(BaseModel):
    """The full ordered stack of sources that could define config for a key."""

    source: Source
    project_id: UUID | None = None
    layers: list[PrecedenceLayer] = []
