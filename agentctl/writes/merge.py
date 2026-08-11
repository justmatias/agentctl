"""Key-scoped merge helper: touch only tool-owned keys in a shared JSON file.

SPECS.md §7.3: writes must never clobber unrelated settings in a shared
file like `settings.json`. `dict` preserves insertion order, so merging
into the parsed object (rather than rebuilding it) keeps every untouched
key's value, position, and presence exactly as found.
"""

import json
from pathlib import Path
from typing import Any

from agentctl.utils import logger

from .atomic import atomic_write


def merge_json_keys(
    path: Path | str, updates: dict[str, Any], *, indent: int = 2
) -> None:
    """Set each top-level key in `updates` on the JSON object at `path`.

    Keys not present in `updates` are left byte-for-byte alone in content;
    only their relative order is subject to how `json.dumps` renders the
    merged object. A missing file is treated as `{}`.
    """
    path = Path(path)
    existing: Any = (
        json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    )
    if not isinstance(existing, dict):
        raise TypeError(
            f"{path} does not contain a JSON object at its root "
            f"(found {type(existing).__name__}); cannot merge keys into it"
        )
    existing.update(updates)
    atomic_write(path, json.dumps(existing, indent=indent) + "\n")
    logger.info(f"Merged keys {sorted(updates)} into {path}")
