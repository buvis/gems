from __future__ import annotations

import logging
from pathlib import Path

from buvis.pybase.filesystem.dir_tree.safe_rglob import safe_rglob

logger = logging.getLogger(__name__)


def delete_by_extension(directory: Path, extensions_to_delete: list[str]) -> None:
    """Delete files with specific extensions in the given directory.

    Args:
        directory: Path to the directory to process.
        extensions_to_delete: List of file extensions to delete.
    """
    for file_path in safe_rglob(directory):
        if file_path.parent.stem == ".stfolder":  ## keep content of sensitive folders
            continue
        if file_path.is_file() and file_path.suffix.lower() in extensions_to_delete:
            file_path.unlink()
            logger.info("Removed extra file %s", file_path)
