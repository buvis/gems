from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_attention(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every sysup test's state and notification settings isolated."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("NTFY_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("BUVIS_SYSUP_AUTO_UPDATE", "false")
    monkeypatch.setattr("buvis.pybase.configuration.click_integration._run_update_check_once", lambda _ctx: None)
