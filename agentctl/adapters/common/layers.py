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


def project_directories(
    working_directory: Path, *, ascend_outside_git: bool = False
) -> tuple[Path, ...]:
    directory = working_directory.resolve()
    directories = (directory, *directory.parents)
    for index, candidate in enumerate(directories):
        git_marker = candidate / ".git"
        if git_marker.is_file() or (git_marker / "HEAD").is_file():
            return directories[: index + 1]
    return directories if ascend_outside_git else (working_directory,)
