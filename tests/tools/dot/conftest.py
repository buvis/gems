from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def dotfiles_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "dotfiles"
    root.mkdir()
    monkeypatch.setenv("DOTFILES_ROOT", str(root))
    return root
