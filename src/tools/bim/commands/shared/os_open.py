from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def open_in_os(path: Path | str) -> None:
    """Open a file using the platform default application."""
    system = platform.system()
    target = str(path)
    if system == "Darwin":
        subprocess.Popen(["open", target])  # noqa: S603
    elif system == "Linux":
        subprocess.Popen(["xdg-open", target])  # noqa: S603
    else:
        import os
        os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
