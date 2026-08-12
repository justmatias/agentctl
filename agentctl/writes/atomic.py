import os
import stat
import tempfile
from pathlib import Path

from agentctl.utils import logger


def _write_to_temp(tmp_path: Path, content: str, encoding: str) -> None:
    with open(tmp_path, "w", encoding=encoding) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def atomic_write(path: Path | str, content: str, *, encoding: str = "utf-8") -> None:
    """Write `content` to `path` so a reader never observes a partial write.

    The destination is only ever touched by `os.replace`, which is atomic on
    POSIX: either the whole new content lands, or the original file (if any)
    is left exactly as it was. If anything fails before the replace — a
    write error, a crash — the temp file is removed and the original is
    never touched.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        _write_to_temp(tmp_path, content, encoding)
        if path.exists():
            os.chmod(tmp_path, stat.S_IMODE(os.stat(path).st_mode))
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    logger.debug(f"Atomically wrote {path}")
