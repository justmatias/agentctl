from pathlib import Path

from agentctl.adapters import SourceAdapter, WalkUpStop
from agentctl.domain import (
    CanonicalConfig,
    ConsultedLayer,
    Extension,
    ExtensionType,
    PrecedenceChain,
)

# The contract every registered SourceAdapter must satisfy, so a new harness
# inherits the whole suite just by joining ADAPTER_FACTORIES. Behaviour specific
# to one harness belongs in that harness's own test module.


def test_adapter_implements_the_source_adapter_protocol(adapter: SourceAdapter) -> None:
    assert isinstance(adapter, SourceAdapter)


def test_adapter_source_matches_its_declared_capabilities(
    adapter: SourceAdapter,
) -> None:
    assert adapter.source == adapter.capabilities.source


def test_adapter_declares_at_least_one_extension_type_and_scope(
    adapter: SourceAdapter,
) -> None:
    assert adapter.capabilities.extension_types
    assert adapter.capabilities.scopes


def test_locate_finds_nothing_in_an_untouched_home_and_project(
    adapter: SourceAdapter, empty_project_root: Path
) -> None:
    assert adapter.locate_global_config() == []
    assert adapter.locate_project_config(empty_project_root) == []


def test_parse_ignores_a_path_that_does_not_exist(
    adapter: SourceAdapter, tmp_path: Path
) -> None:
    assert adapter.parse(tmp_path / "absent.json") == []


def test_parse_ignores_a_file_the_source_does_not_recognize(
    adapter: SourceAdapter, tmp_path: Path
) -> None:
    unrecognized_file = tmp_path / "notes.txt"
    unrecognized_file.write_text("not config\n")

    assert adapter.parse(unrecognized_file) == []


def test_precedence_chain_reports_the_adapters_own_source(
    adapter: SourceAdapter, precedence_chain: PrecedenceChain
) -> None:
    assert precedence_chain.source == adapter.source


def test_consulted_layers_are_ranked_uniquely_and_in_ascending_order(
    precedence_chain: PrecedenceChain,
) -> None:
    ranks = [
        layer.order_rank
        for layer in precedence_chain.layers
        if isinstance(layer, ConsultedLayer)
    ]

    assert ranks == sorted(ranks)
    assert len(ranks) == len(set(ranks))


def test_only_consulted_layers_can_resolve(
    precedence_chain: PrecedenceChain,
) -> None:
    unresolvable = [
        layer
        for layer in precedence_chain.layers
        if not isinstance(layer, ConsultedLayer)
    ]

    assert all(layer.resolves is False for layer in unresolvable)


def test_every_layer_names_where_it_would_come_from(
    precedence_chain: PrecedenceChain,
) -> None:
    assert precedence_chain.layers
    assert all(layer.file_path for layer in precedence_chain.layers)


def test_walk_up_behavior_agrees_with_where_the_ascent_stops(
    adapter: SourceAdapter,
) -> None:
    for extension_type in adapter.capabilities.extension_types:
        behavior = adapter.walk_up_behavior(extension_type)
        if behavior.ascends:
            assert behavior.stops_at != WalkUpStop.NONE
        else:
            assert behavior.stops_at == WalkUpStop.NONE


def test_serialize_renders_every_extension_type_the_adapter_declares(
    adapter: SourceAdapter, canonical_configs: dict[ExtensionType, CanonicalConfig]
) -> None:
    for extension_type in adapter.capabilities.extension_types:
        extension = Extension(
            name="sample",
            origin_harness=adapter.source,
            canonical_config=canonical_configs[extension_type],
        )

        assert adapter.serialize(extension)
