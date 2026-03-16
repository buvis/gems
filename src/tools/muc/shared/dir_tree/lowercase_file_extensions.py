from __future__ import annotations

import logging
from pathlib import Path

from .safe_rglob import safe_rglob

logger = logging.getLogger(__name__)


def lowercase_file_extensions(directory: Path) -> None:
    """Convert all file extensions to lowercase in the given directory.

    Args:
        directory: Path to the directory to process.
    """
    for file_path in safe_rglob(directory):
        if file_path.is_file():
            new_name = file_path.stem + file_path.suffix.lower()
            new_path = file_path.with_name(new_name)

            if new_path != file_path:
                file_path.rename(new_path)
                logger.info("Renamed %s -> %s", file_path, new_name)
