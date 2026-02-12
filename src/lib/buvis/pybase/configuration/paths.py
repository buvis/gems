from __future__ import annotations

import os
from pathlib import Path


def get_config_dirs() -> list[Path]:
    """Config dirs in priority order (highest first).

    1. $BUVIS_CONFIG_DIR (if set and non-empty)
    2. ~/.config/buvis (default)
    """
    dirs: list[Path] = []
    if env_dir := os.getenv("BUVIS_CONFIG_DIR"):
        dirs.append(Path(env_dir).expanduser())
    dirs.append(Path.home() / ".config" / "buvis")
    return dirs
