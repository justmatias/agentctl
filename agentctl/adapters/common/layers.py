from pathlib import Path

from agentctl.domain import ConsultedLayer, LayerOrigin, Scope


def consulted_file_layer(
    *, scope: Scope, path: Path, origin: LayerOrigin, order_rank: int
) -> ConsultedLayer:
    """A file-backed layer the adapter has verified is consulted.

    A file-backed layer resolves exactly when it exists on disk, so `exists`
    and `resolves` are derived together from a single stat.
    """
    exists = path.is_file()
    return ConsultedLayer(
        scope=scope,
        file_path=str(path),
        exists=exists,
        origin=origin,
        order_rank=order_rank,
        resolves=exists,
    )
