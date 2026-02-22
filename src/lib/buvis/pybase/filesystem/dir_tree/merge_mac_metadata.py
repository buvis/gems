from __future__ import annotations

import logging
import os
from pathlib import Path

from buvis.pybase.filesystem.dir_tree.safe_rglob import safe_rglob

if os.name != "nt":
    import xattr

logger = logging.getLogger(__name__)


def merge_mac_metadata(directory: Path) -> None:
    """Clean Mac metadata by merging extended attributes and removing ._ files.

    Mimics the behavior of 'dot_clean -mn':
    - For each ._ file, tries to merge its contents into the corresponding data file.
    - If merging is successful, removes the ._ file.
    - If there's no corresponding data file, removes the ._ file.

    Args:
        directory: Path to the directory to process.
    """
    for apple_double in safe_rglob(directory, "._*"):
        if apple_double.is_file():
            data_file = apple_double.with_name(apple_double.name[2:])
            if os.name != "nt" and data_file.exists():
                try:
                    # Read the resource fork from the ._ file
                    with apple_double.open("rb") as f:
                        resource_fork = f.read()

                    # Set the resource fork as an extended attribute on the data file
                    xattr.setxattr(
                        str(data_file),
                        "com.apple.ResourceFork",
                        resource_fork,
                    )

                    # Remove the ._ file
                    apple_double.unlink()
                    logger.info(
                        "Merged metadata from %s to %s",
                        apple_double,
                        data_file,
                    )
                except OSError:
                    pass
            else:
                # If there's no corresponding data file, just remove the ._ file
                try:
                    apple_double.unlink()
                    logger.info("Deleted %s", apple_double)
                except OSError:
                    pass
