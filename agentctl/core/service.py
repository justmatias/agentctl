import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import file_digest, sha256
from pathlib import Path
from typing import NamedTuple

from sqlmodel import col, select

from agentctl.adapters import AdapterRegistry, SourceAdapter
from agentctl.domain import (
    Binding,
    Extension,
    ExtensionType,
    McpServerConfig,
    Scope,
    SkillConfig,
    Source,
    SyncState,
)
from agentctl.storage import Database
from agentctl.storage.schema import BindingRow, ExtensionRow
from agentctl.utils import logger

from .inventory import InventoryClassification, InventoryItem


class InventoryKey(NamedTuple):
    source: Source
    scope: Scope
    path: Path
    extension_type: ExtensionType
    name: str


class InventoryObservation(NamedTuple):
    extension: Extension
    content_hash: str


@dataclass
class CoreService:
    """Owns adapter discovery and the storage connection for one process."""

    registry: AdapterRegistry
    database: Database

    def registered_sources(self) -> list[Source]:
        """Every source currently registered, in registration order."""
        return [adapter.source for adapter in self.registry.list()]

    def scan_inventory(self) -> list[InventoryItem]:
        """Read the current machine-wide inventory and persist its observations."""
        discovered = self._discover_extensions()
        session = self.database.session
        try:
            inventory = self._store_observations(discovered)
            session.commit()
        except Exception:
            session.rollback()
            raise
        return inventory

    def _discover_extensions(self) -> dict[InventoryKey, InventoryObservation]:
        discovered: dict[InventoryKey, InventoryObservation] = {}
        for adapter in self.registry.list():
            for location in sorted(set(adapter.locate_scoped_global_config())):
                path = location.path.absolute()
                for observation in _read_observations(adapter, path, location.scope):
                    extension = observation.extension
                    key = InventoryKey(
                        adapter.source,
                        location.scope,
                        path,
                        extension.type,
                        extension.name,
                    )
                    discovered.setdefault(key, observation)
        return discovered

    def _store_observations(
        self, discovered: dict[InventoryKey, InventoryObservation]
    ) -> list[InventoryItem]:
        session = self.database.session
        query = (
            select(BindingRow, ExtensionRow)
            .join(ExtensionRow, col(BindingRow.extension_id) == col(ExtensionRow.id))
            .order_by(col(BindingRow.id))
        )
        existing: dict[InventoryKey, tuple[BindingRow, ExtensionRow]] = {}
        binding_counts: Counter[str] = Counter()
        for binding, extension in session.exec(query):
            binding_counts[extension.id] += 1
            key = InventoryKey(
                Source(binding.harness),
                Scope(binding.scope),
                Path(binding.file_path).absolute(),
                ExtensionType(extension.type),
                extension.name,
            )
            existing.setdefault(key, (binding, extension))

        return [
            self._observe_extension(
                key, observation, existing.get(key), binding_counts
            )
            for key, observation in sorted(discovered.items())
        ]

    def _observe_extension(
        self,
        key: InventoryKey,
        observation: InventoryObservation,
        rows: tuple[BindingRow, ExtensionRow] | None,
        binding_counts: Counter[str],
    ) -> InventoryItem:
        parsed = observation.extension
        canonical = parsed.canonical_config
        config = canonical.model_dump(mode="json")
        if rows is None:
            extension_row = ExtensionRow(**parsed.model_dump(mode="json"))
            binding = Binding(
                extension_id=parsed.id,
                harness=key.source,
                scope=key.scope,
                file_path=str(key.path),
                enabled=canonical.enabled
                if isinstance(canonical, McpServerConfig)
                else True,
                sync_state=SyncState.UNADOPTED,
                last_seen_hash=observation.content_hash,
            )
            session = self.database.session
            session.add(extension_row)
            session.flush()
            session.add(BindingRow(**binding.model_dump(mode="json")))
        else:
            binding_row, extension_row = rows
            binding_row.last_seen_hash = observation.content_hash
            if isinstance(canonical, McpServerConfig):
                binding_row.enabled = canonical.enabled
            if (
                binding_row.sync_state == SyncState.UNADOPTED
                and binding_counts[extension_row.id] == 1
                and extension_row.canonical_config != config
            ):
                extension_row.canonical_config = config
                extension_row.updated_at = datetime.now(UTC).isoformat()
            binding = Binding.model_validate(binding_row.model_dump())

        return InventoryItem(
            extension=Extension.model_validate({
                **extension_row.model_dump(),
                "canonical_config": config,
            }),
            binding=binding,
            classification=_classify_binding(binding.sync_state),
        )


def _read_observations(
    adapter: SourceAdapter, path: Path, scope: Scope
) -> list[InventoryObservation]:
    try:
        extensions = adapter.parse(path, scope=scope)
    except (OSError, UnicodeDecodeError) as error:
        logger.warning(f"Skipping unreadable config {path}: {type(error).__name__}")
        return []
    if not extensions and not path.exists():
        logger.warning(f"Skipping config that disappeared during scan: {path}")

    observations = []
    for extension in extensions:
        try:
            content_hash = _hash_config(path, extension)
        except OSError as error:
            logger.warning(f"Skipping unreadable bundle for {path}: {type(error).__name__}")
            continue
        observations.append(InventoryObservation(extension, content_hash))
    return observations


def _hash_config(path: Path, extension: Extension) -> str:
    canonical = extension.canonical_config
    config = canonical.model_dump(mode="json")
    digest = sha256(json.dumps(config, sort_keys=True).encode("utf-8"))
    if isinstance(canonical, SkillConfig):
        for relative_path in sorted(canonical.bundled_files):
            with (path.parent / relative_path).open("rb") as bundle:
                digest.update(file_digest(bundle, "sha256").digest())
    return digest.hexdigest()


def _classify_binding(state: SyncState) -> InventoryClassification:
    if state == SyncState.UNMANAGED:
        return InventoryClassification.UNMANAGED
    if state in {SyncState.UNADOPTED, SyncState.DRIFTED}:
        return InventoryClassification.NEEDS_REVIEW
    return InventoryClassification.ADOPTED
