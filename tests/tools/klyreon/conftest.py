from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Callable

FIXTURES = Path(__file__).parent / "fixtures"
VALID_CORPUS = FIXTURES / "valid"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def valid_corpus() -> Path:
    """Path to the hand-authored, byte-stable valid fixture vault."""
    return VALID_CORPUS


@pytest.fixture
def empty_vault(tmp_path: Path) -> Path:
    """An initialized-but-empty vault skeleton under tmp_path."""
    root = tmp_path / "vault"
    for sub in ("sources", "wiki/notes", "wiki/mocs", "wiki/trails"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def copied_valid_vault(tmp_path: Path) -> Path:
    """A writable copy of the valid corpus."""
    root = tmp_path / "vault"
    shutil.copytree(VALID_CORPUS, root)
    return root


@pytest.fixture
def klyreon_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[Path], None]:
    """Factory that points $KLYREON_ROOT at a given vault and isolates XDG dirs."""

    def _point(root: Path) -> None:
        monkeypatch.setenv("KLYREON_ROOT", str(root))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    return _point


@pytest.fixture
def frozen_now() -> dt.datetime:
    return dt.datetime(2026, 4, 11, 14, 53, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
