from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Connection

from agentctl.core import CoreService, InventoryClassification, InventoryItem
from agentctl.domain import Scope, Source, SyncState
from agentctl.storage import (
    Database,
    SqliteBindingRepository,
    SqliteExtensionRepository,
)


@pytest.mark.usefixtures("installed_config")
def test_scan_returns_ordered_inventory_when_all_sources_are_present(
    service: CoreService,
) -> None:
    def _describe_inventory(
        items: list[InventoryItem],
    ) -> list[tuple[Source, Scope, str, str | None]]:
        return [
            (
                item.binding.harness,
                item.binding.scope,
                item.extension.name,
                item.binding.last_seen_hash,
            )
            for item in items
        ]

    first = service.scan_inventory()
    assert [(item.binding.harness, item.binding.scope) for item in first] == [
        (Source.CLAUDE_CODE, Scope.USER),
        (Source.CLAUDE_CODE, Scope.USER),
        (Source.CODEX_CLI, Scope.MANAGED),
        (Source.CURSOR, Scope.USER),
        (Source.DOT_AGENTS, Scope.GLOBAL),
        (Source.OPENCODE, Scope.USER),
    ]
    assert [item.extension.name for item in first[:2]] == ["alpha", "beta"]
    assert all(
        item.classification == InventoryClassification.NEEDS_REVIEW for item in first
    )
    assert all(len(item.binding.last_seen_hash or "") == 64 for item in first)
    extensions = SqliteExtensionRepository(service.database.session)
    bindings = SqliteBindingRepository(service.database.session)
    before = (extensions.list(), bindings.list(order_by="id"))
    assert service.scan_inventory() == first
    assert (extensions.list(), bindings.list(order_by="id")) == before
    with Database() as rebuilt:
        assert _describe_inventory(
            CoreService(service.registry, rebuilt).scan_inventory()
        ) == (_describe_inventory(first))


def test_scan_updates_one_hash_when_one_server_changes(
    service: CoreService,
    installed_config: dict[str, Path],
) -> None:
    first = service.scan_inventory()
    path = installed_config[".claude.json"]
    path.write_text(path.read_text().replace('"one"', '"changed"'))
    second = service.scan_inventory()
    assert first[0].binding.last_seen_hash != second[0].binding.last_seen_hash
    assert first[0].binding.id == second[0].binding.id
    assert first[1:] == second[1:]


@pytest.mark.usefixtures("installed_config")
def test_scan_preserves_saved_classification_when_bindings_have_user_state(
    service: CoreService,
) -> None:
    repository = SqliteBindingRepository(service.database.session)
    first = service.scan_inventory()
    states = [SyncState.IN_SYNC, SyncState.DRIFTED, SyncState.UNMANAGED]
    for item, state in zip(first[:3], states, strict=True):
        repository.update(
            item.binding.model_copy(
                update={
                    "sync_state": state,
                    "last_written_hash": "saved",
                }
            )
        )
    second = service.scan_inventory()
    assert [item.classification for item in second[:3]] == [
        InventoryClassification.ADOPTED,
        InventoryClassification.NEEDS_REVIEW,
        InventoryClassification.UNMANAGED,
    ]
    assert [item.binding.sync_state for item in second[:3]] == states
    assert all(item.binding.last_written_hash == "saved" for item in second[:3])


def test_scan_omits_entries_when_a_file_is_removed(
    service: CoreService,
    installed_config: dict[str, Path],
) -> None:
    first = service.scan_inventory()
    installed_config[".claude.json"].unlink()
    assert service.scan_inventory() == first[2:]


@pytest.mark.usefixtures("installed_config")
def test_scan_rolls_back_observations_when_binding_write_fails(
    service: CoreService,
) -> None:
    def reject_binding_insert(
        _connection: Connection,
        _cursor: object,
        statement: str,
        *_arguments: object,
    ) -> None:
        if statement.startswith("INSERT INTO bindings"):
            raise ValueError("binding write failed")

    connection = service.database.connection
    event.listen(connection, "before_cursor_execute", reject_binding_insert)
    try:
        with pytest.raises(ValueError, match="binding write failed"):
            service.scan_inventory()
    finally:
        event.remove(connection, "before_cursor_execute", reject_binding_insert)
    assert SqliteExtensionRepository(service.database.session).list() == []
    assert SqliteBindingRepository(service.database.session).list() == []


def test_scan_reports_binding_disabled_when_codex_config_disables_server(
    service: CoreService,
    installed_config: dict[str, Path],
) -> None:
    path = installed_config["system/config.toml"]
    enabled = next(
        item.binding
        for item in service.scan_inventory()
        if item.binding.harness == Source.CODEX_CLI
    )
    path.write_text(path.read_text() + "\nenabled = false\n")
    disabled = next(
        item.binding
        for item in service.scan_inventory()
        if item.binding.harness == Source.CODEX_CLI
    )
    assert enabled.enabled
    assert not disabled.enabled
    assert disabled.id == enabled.id
    assert disabled.last_seen_hash != enabled.last_seen_hash
    repository = SqliteBindingRepository(service.database.session)
    assert repository.get(disabled.id) == disabled


def test_scan_preserves_canonical_config_when_multiple_bindings_share_it(
    service: CoreService,
    installed_config: dict[str, Path],
) -> None:
    first, second, *_remaining = service.scan_inventory()
    bindings = SqliteBindingRepository(service.database.session)
    extensions = SqliteExtensionRepository(service.database.session)
    bindings.update(
        second.binding.model_copy(
            update={
                "extension_id": first.extension.id,
                "sync_state": SyncState.IN_SYNC,
                "harness": Source.CODEX_CLI,
            }
        )
    )
    path = installed_config[".claude.json"]
    path.write_text(path.read_text().replace('"one"', '"changed"'))

    observed = service.scan_inventory()[0]

    assert observed.extension.canonical_config != first.extension.canonical_config
    assert extensions.get(first.extension.id) == first.extension
