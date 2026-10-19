"""Git clean/smudge byte transforms that swap the host home path for a token."""

from __future__ import annotations

import os
import re
from pathlib import Path

TOKEN = b"@HOME@"

_WORD = rb"[A-Za-z0-9._-]"
_WINDOWS_HOME = re.compile(r"^[A-Za-z]:[/\\]")


def _normalize(home: str) -> str:
    """Return home with Windows backslashes turned into forward slashes."""
    if _WINDOWS_HOME.match(home):
        return home.replace("\\", "/")
    return home


def _pattern(home: str) -> re.Pattern[bytes]:
    """Compile a boundary-checked matcher for every accepted spelling of home."""
    home = _normalize(home)
    if _WINDOWS_HOME.match(home):
        drive = re.escape(os.fsencode(home[0].upper() + home[0].lower()))
        parts = [re.escape(os.fsencode(part)) for part in home[3:].split("/")]
        spellings = [b"[" + drive + b"]:" + sep + sep.join(parts) for sep in (rb"\\", rb"\\\\", b"/")]
        body = b"(?:" + b"|".join(spellings) + b")"
    else:
        body = re.escape(os.fsencode(home))
    return re.compile(b"(?<!" + _WORD + b")" + body + b"(?!" + _WORD + b")")


def clean(data: bytes, home: str) -> bytes:
    """Replace each boundary-matched home path in data with TOKEN.

    Raises:
        ValueError: If data already contains TOKEN.
    """
    if TOKEN in data:
        msg = f"input already contains reserved token {TOKEN.decode()}"
        raise ValueError(msg)
    return _pattern(home).sub(TOKEN, data)


def smudge(data: bytes, home: str) -> bytes:
    """Replace each TOKEN in data with home (Windows homes use forward slashes)."""
    return data.replace(TOKEN, os.fsencode(_normalize(home)))


def count_home(data: bytes, home: str) -> int:
    """Count boundary-matched home paths in data."""
    return len(_pattern(home).findall(data))


def resolve_home(work_tree: str | None, cwd: str) -> str:
    """Resolve the home path from the git work tree, DOTFILES_ROOT, or HOME."""
    if work_tree:
        home = str(Path(cwd, work_tree))
    else:
        dotfiles_root = os.environ.get("DOTFILES_ROOT")
        home = str(Path(dotfiles_root)) if dotfiles_root else str(Path.home())
    if _WINDOWS_HOME.match(home):
        return _normalize(home).rstrip("/\\")
    return home
