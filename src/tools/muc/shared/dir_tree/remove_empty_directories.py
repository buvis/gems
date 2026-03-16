from __future__ import annotations

import logging
from pathlib import Path

from .safe_rglob import safe_rglob

logger = logging.getLogger(__name__)


def remove_empty_directories(directory: Path) -> None:
    """Remove empty directories in the given directory.

    Args:
        directory: Path to the directory to process.
    """
    for dir_path in sorted(safe_rglob(directory), reverse=True):
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            dir_path.rmdir()
            logger.info("Removed empty directory %s", dir_path)
