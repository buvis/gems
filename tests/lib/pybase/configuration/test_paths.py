from __future__ import annotations

from pathlib import Path

import pytest
from buvis.pybase.configuration.paths import get_config_dirs


class TestGetConfigDirs:
    def test_default_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BUVIS_CONFIG_DIR", raising=False)

        dirs = get_config_dirs()

        assert dirs == [Path.home() / ".config" / "buvis"]

    def test_with_buvis_config_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "/custom/config")

        dirs = get_config_dirs()

        assert dirs[0] == Path("/custom/config")
        assert dirs[1] == Path.home() / ".config" / "buvis"
        assert len(dirs) == 2

    def test_empty_env_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "")

        dirs = get_config_dirs()

        assert len(dirs) == 1
        assert dirs[0] == Path.home() / ".config" / "buvis"

    def test_tilde_expanded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "~/my-config")

        dirs = get_config_dirs()

        assert dirs[0] == Path.home() / "my-config"
