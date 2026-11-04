from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

STATE_VERSION = 1
SKILL_NAME = re.compile(r"^name:\s*[\"']?([a-z0-9-]+)[\"']?\s*$")
AGENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class BraidError(RuntimeError):
    """A safe, user-actionable composition failure."""


class Mode(str, Enum):
    SYNC = "sync"
    DRY_RUN = "dry-run"
    CHECK = "check"


@dataclass(frozen=True)
class Settings:
    sources: tuple[Path, ...]
    agents_root: Path
    claude_root: Path
    mode: Mode = Mode.SYNC
    policy_files: tuple[Path, ...] = ()
    project_claude: bool = True
    platform: str = os.name
    enable_kiro: bool = False
    kiro_root: Path | None = None
    kiro_agents: tuple[str, ...] = ()
    forget_kiro_agents: tuple[str, ...] = ()
    project_kiro: bool = True

    def with_mode(self, mode: Mode) -> Settings:
        return replace(self, mode=mode)


@dataclass
class Result:
    linked: int = 0
    current: int = 0
    ignored: int = 0
    removed: int = 0
    backed_up: int = 0
    drift: int = 0
    configured: int = 0


def _present(path: Path) -> bool:
    return os.path.lexists(path)


def _expand_user(path: str | Path) -> Path:
    value = os.fspath(path)
    if value == "~":
        return Path.home()
    if value.startswith(("~/", "~\\")):
        return Path.home() / value[2:]
    return Path(value).expanduser()


def _resolved(path: Path) -> Path:
    return _expand_user(path).resolve(strict=False)


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(_expand_user(path)))
