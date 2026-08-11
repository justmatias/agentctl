"""Safe write layer: atomic writes, backups/rollback, key-scoped merges (ROADMAP.md PR 0.3)."""

from .atomic import atomic_write
from .backup import Backup, RollbackIndex
from .merge import merge_json_keys

__all__ = [
    "Backup",
    "RollbackIndex",
    "atomic_write",
    "merge_json_keys",
]
