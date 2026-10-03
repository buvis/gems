"""Vault root discovery and path confinement, with the confinement oracle probe."""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.vault.config import RootError, resolve_root
from klyreon.vault.paths import PathConfinementError, is_confined, resolve_path


class TestRootDiscovery:
    def test_env_root_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        root = tmp_path / "env-root"
        root.mkdir()
        cfg_dir = tmp_path / "config"
        (cfg_dir / "klyreon").mkdir(parents=True)
        other = tmp_path / "other"
        other.mkdir()
        (cfg_dir / "klyreon" / "config.yaml").write_text(f"root: {other}\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg_dir))
        monkeypatch.setenv("KLYREON_ROOT", str(root))
        assert resolve_root() == root.resolve()

    def test_config_file_used_when_env_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        root = tmp_path / "cfg-root"
        root.mkdir()
        cfg_dir = tmp_path / "config"
        (cfg_dir / "klyreon").mkdir(parents=True)
        (cfg_dir / "klyreon" / "config.yaml").write_text(f"root: {root}\n")
        monkeypatch.delenv("KLYREON_ROOT", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg_dir))
        assert resolve_root() == root.resolve()

    def test_relative_root_fails_loudly(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KLYREON_ROOT", "relative/path")
        with pytest.raises(RootError, match="absolute"):
            resolve_root()

    def test_missing_root_directory_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KLYREON_ROOT", str(tmp_path / "nope"))
        with pytest.raises(RootError, match="does not exist"):
            resolve_root()

    def test_missing_config_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("KLYREON_ROOT", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-config"))
        with pytest.raises(RootError, match="config file is missing"):
            resolve_root()

    def test_config_without_root_key_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg_dir = tmp_path / "config"
        (cfg_dir / "klyreon").mkdir(parents=True)
        (cfg_dir / "klyreon" / "config.yaml").write_text("other: 1\n")
        monkeypatch.delenv("KLYREON_ROOT", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg_dir))
        with pytest.raises(RootError, match="no 'root' key"):
            resolve_root()


class TestPathConfinement:
    def test_simple_relative_resolves(self, tmp_path: Path) -> None:
        resolved = resolve_path(tmp_path, "wiki/notes/x.md")
        assert resolved == (tmp_path / "wiki/notes/x.md").resolve()

    def test_dotdot_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathConfinementError, match=r"\.\."):
            resolve_path(tmp_path, "../escape.md")

    def test_absolute_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathConfinementError, match="absolute"):
            resolve_path(tmp_path, "/etc/passwd")

    def test_is_confined_bool(self, tmp_path: Path) -> None:
        assert is_confined(tmp_path, "wiki/notes/x.md") is True
        assert is_confined(tmp_path, "../x.md") is False


class TestProbePathConfinement:
    """Independent oracle: hand-chosen escaping inputs that a naive join misses."""

    def test_escaping_inputs_all_rejected(self, tmp_path: Path) -> None:
        root = (tmp_path / "vault").resolve()
        root.mkdir()
        escapes = [
            "../secrets.md",
            "wiki/../../outside.md",
            "a/b/../../../c.md",
            "/absolute/evil.md",
        ]
        for rel in escapes:
            assert is_confined(root, rel) is False, f"{rel!r} should be rejected"
        # And a legitimately deep but confined path is accepted.
        assert is_confined(root, "sources/archive/2026-04/a.md") is True
