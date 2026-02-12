import logging
from pathlib import Path

from buvis.pybase.filesystem.dir_tree.safe_rglob import safe_rglob


def lowercase_file_extensions(directory: Path) -> None:
    """
    Convert all file extensions to lowercase in the given directory.

    :param directory: Path to the directory to process
    :type directory: :class:`Path`
    :return: None. The function modifies the <directory> in place.
    """
    for file_path in safe_rglob(directory):
        if file_path.is_file():
            new_name = file_path.stem + file_path.suffix.lower()
            new_path = file_path.with_name(new_name)

            if new_path != file_path:
                file_path.rename(new_path)
                logging.info("Renamed %s -> %s", file_path, new_name)
