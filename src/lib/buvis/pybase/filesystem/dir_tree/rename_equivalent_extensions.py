from __future__ import annotations

import logging
from pathlib import Path

from buvis.pybase.filesystem.dir_tree.safe_rglob import safe_rglob


def rename_equivalent_extensions(
    directory: Path,
    equivalent_extensions: list[list[str]],
) -> None:
    """
    Rename files based on equivalent extensions.

    :param directory: Path to the directory to process
    :type directory: :class:`Path`
    :param equivalent_extensions: List of lists containing equivalent extensions.
        First item is the target the rest of the list will be renamed to
    :type equivalent_extensions: List[List[str]]
    :return: None. The function modifies the <directory> in place.
    """
    directory = Path(directory)
    extension_map = {}
    for group in equivalent_extensions:
        target = "." + group[0].lower()
        for ext in group[1:]:
            extension_map["." + ext.lower()] = target

    for file_path in safe_rglob(directory):
        if file_path.is_file():
            current_ext = file_path.suffix.lower()
            if current_ext in extension_map:
                new_ext = extension_map[current_ext]
                new_name = file_path.stem + new_ext
                new_path = file_path.with_name(new_name)
                file_path.rename(new_path)
                logging.info("Renamed %s -> %s", file_path, new_name)
