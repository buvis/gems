"""Tiromex folder resolution, path confinement, note listing and tx state."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, slots=True)
class TiromexPaths:
    """Resolved vault root, zettelkasten and tiromex folder."""

    vault_root: Path
    zettelkasten: Path
    folder: Path


def resolve_tiromex(path_zettelkasten: Path, folder_name: str) -> TiromexPaths:
    """Resolve the tiromex folder inside the zettelkasten.

    Args:
        path_zettelkasten: The zettelkasten directory (may be relative or a symlink).
        folder_name: A single-part folder name under the zettelkasten.

    Returns:
        The resolved paths. The folder is not created.

    Raises:
        ValueError: When the folder name is not one plain part, the zettelkasten
            is not a directory, or the folder is a symlink or resolves elsewhere.
    """
    name = Path(folder_name)
    if not folder_name or name.is_absolute() or len(name.parts) != 1 or folder_name in {".", ".."}:
        raise ValueError(f"tiromex folder must be a single folder name: {folder_name!r}")
    zettelkasten = path_zettelkasten.expanduser().resolve()
    if not zettelkasten.is_dir():
        raise ValueError(f"zettelkasten is not a directory: {zettelkasten}")
    folder = zettelkasten / folder_name
    if folder.is_symlink() or folder.resolve() != folder:
        raise ValueError(f"tiromex folder must not be a symlink: {folder}")
    return TiromexPaths(vault_root=zettelkasten.parent, zettelkasten=zettelkasten, folder=folder)


def confine(paths: TiromexPaths, vault_rel: str) -> Path:
    """Resolve a vault-relative POSIX path and assert it stays in the tiromex folder.

    Args:
        paths: The resolved tiromex paths.
        vault_rel: A path relative to the vault root, e.g. ``notes/tiromex/<id>.md``.

    Returns:
        The resolved path. The file need not exist.

    Raises:
        ValueError: When the path is absolute, has a ``..`` part, or resolves
            (symlinks followed) outside the tiromex folder.
    """
    rel = PurePosixPath(vault_rel)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"path must be vault-relative without '..': {vault_rel!r}")
    resolved = (paths.vault_root / rel).resolve()
    if not resolved.is_relative_to(paths.folder):
        raise ValueError(f"path is outside the tiromex folder: {vault_rel!r}")
    return resolved


def to_vault_rel(paths: TiromexPaths, file: Path) -> str:
    """Return the POSIX path of ``file`` relative to the vault root."""
    return file.relative_to(paths.vault_root).as_posix()


def iter_note_files(paths: TiromexPaths) -> list[Path]:
    """Return the sorted ``*.md`` files under the tiromex folder, recursively.

    Files whose resolved path leaves the folder are left out. A missing folder
    gives an empty list.
    """
    if not paths.folder.is_dir():
        return []
    return sorted(
        file for file in paths.folder.rglob("*.md") if file.is_file() and file.resolve().is_relative_to(paths.folder)
    )


def tx_state_dir() -> Path:
    """Return ``$XDG_STATE_HOME/bim/tx``, else ``~/.local/state/bim/tx``."""
    xdg = os.environ.get("XDG_STATE_HOME", "")
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".local" / "state"
    return base / "bim" / "tx"


def read_last_maintain() -> str | None:
    """Return the ``last_maintain`` string from the tx state file.

    Returns:
        The stored string, or ``None`` when the file is absent, unreadable,
        not a JSON object, or holds no string under ``last_maintain``.
    """
    try:
        data = json.loads((tx_state_dir() / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("last_maintain")
    return value if isinstance(value, str) else None
