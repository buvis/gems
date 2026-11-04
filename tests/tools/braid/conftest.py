from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_braid_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the developer's own braid env, config, HOME and cwd out of every braid test."""
    for name in list(os.environ):
        if name.startswith("BUVIS_BRAID_"):
            monkeypatch.delenv(name)
    config_dir = tmp_path / "buvis-config"
    config_dir.mkdir()
    monkeypatch.setenv("BUVIS_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("BUVIS_DEV_MODE", "1")
    monkeypatch.chdir(tmp_path)
