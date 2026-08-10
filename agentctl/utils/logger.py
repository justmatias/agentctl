from __future__ import annotations

import os
import sys

from loguru import logger

logger.remove()
logger.add(
    sys.stdout,
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}",
    enqueue=True,
)
