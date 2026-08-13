import platform
from pathlib import Path


def platform_specific_path(*, darwin: Path, windows: Path, default: Path) -> Path:
    """Pick the path a source uses on the host operating system.

    Every branch returns, so a source can never silently fall through to
    another platform's path.
    """
    system = platform.system()
    if system == "Darwin":
        return darwin
    if system == "Windows":
        return windows
    return default
