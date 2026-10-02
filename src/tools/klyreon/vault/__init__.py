from __future__ import annotations

from klyreon.vault.config import RootError, config_path, resolve_root
from klyreon.vault.git import (
    GitError,
    GitIdentity,
    commit,
    is_git_vault,
    is_human_authored,
    require_git_for_autonomy,
)
from klyreon.vault.ids import AllocatedId, allocate_id, format_id
from klyreon.vault.paths import PathConfinementError, is_confined, resolve_path
from klyreon.vault.state import read_state, state_path, write_state

__all__ = [
    "AllocatedId",
    "GitError",
    "GitIdentity",
    "PathConfinementError",
    "RootError",
    "allocate_id",
    "commit",
    "config_path",
    "format_id",
    "is_confined",
    "is_git_vault",
    "is_human_authored",
    "read_state",
    "require_git_for_autonomy",
    "resolve_path",
    "resolve_root",
    "state_path",
    "write_state",
]
