"""Phase 1 -- the installer, every branch against a temp HOME."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from klyreon.assets import installer
from klyreon.assets.manifest import load_manifest, manifest_path
from klyreon.assets.registry import payload_files, resolve_target

pytestmark = pytest.mark.klyreon


@pytest.fixture
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME, XDG_STATE_HOME, and CLAUDE_CONFIG_DIR under tmp_path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return home


def _skill_target(home: Path) -> Path:
    return home / ".claude" / "skills" / "klyreon" / "SKILL.md"


def _shipped_bytes() -> bytes:
    _, handle = payload_files("claude")[0]
    return handle.read_bytes()


class TestInstall:
    def test_fresh_install_writes_and_records(self, temp_home: Path) -> None:
        report = installer.install(["claude"])
        target = _skill_target(temp_home)
        assert target.is_file()
        assert target.read_bytes() == _shipped_bytes()
        assert str(target) in report.written
        assert not report.current
        assert not report.displaced

        manifest = load_manifest()
        assert len(manifest.entries) == 1
        entry = manifest.entries[0]
        assert entry.operator == "claude"
        assert entry.kind == "asset"
        assert entry.path == str(target)
        assert entry.sha256

    def test_second_install_is_idempotent_no_rewrite_no_backup(self, temp_home: Path) -> None:
        installer.install(["claude"])
        target = _skill_target(temp_home)
        before = target.stat().st_mtime_ns
        report = installer.install(["claude"])
        assert str(target) in report.current
        assert not report.written
        assert not report.displaced
        assert target.stat().st_mtime_ns == before, "idempotent install must not rewrite the file"
        # No stray backup created.
        backups = list(target.parent.glob("*.klyreon-backup-*"))
        assert backups == []

    def test_edited_file_is_backed_up_then_overwritten(self, temp_home: Path) -> None:
        installer.install(["claude"], now=dt.datetime(2026, 1, 1, 10, 0, 0, tzinfo=dt.timezone.utc))
        target = _skill_target(temp_home)
        target.write_text("my hand edits\n", encoding="utf-8")

        report = installer.install(["claude"], now=dt.datetime(2026, 2, 2, 11, 0, 0, tzinfo=dt.timezone.utc))
        assert str(target) in report.written
        assert len(report.displaced) == 1
        orig, backup = report.displaced[0]
        assert orig == str(target)
        backup_path = Path(backup)
        assert backup_path.is_file()
        assert backup_path.read_text(encoding="utf-8") == "my hand edits\n"
        assert ".klyreon-backup-" in backup_path.name
        # The shipped content is back in place and the manifest hash is updated.
        assert target.read_bytes() == _shipped_bytes()
        entry = load_manifest().entry_for_path(str(target))
        assert entry is not None
        import hashlib

        assert entry.sha256 == hashlib.sha256(_shipped_bytes()).hexdigest()

    def test_untracked_preexisting_file_is_backed_up(self, temp_home: Path) -> None:
        # A file at the target path, absent from the manifest, is the user's.
        target = _skill_target(temp_home)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("pre-existing user file\n", encoding="utf-8")
        assert not manifest_path().exists()

        report = installer.install(["claude"])
        assert len(report.displaced) == 1
        _, backup = report.displaced[0]
        assert Path(backup).read_text(encoding="utf-8") == "pre-existing user file\n"
        assert target.read_bytes() == _shipped_bytes()

    def test_unknown_operator_writes_nothing(self, temp_home: Path) -> None:
        from klyreon.assets.registry import UnknownOperatorError

        with pytest.raises(UnknownOperatorError):
            installer.install(["emacs"])
        assert not _skill_target(temp_home).exists()
        assert not manifest_path().exists()

    def test_recorded_but_unmodified_behind_content_refreshes_without_backup(self, temp_home: Path) -> None:
        # Install, then simulate a newer shipped payload by rewriting the manifest
        # hash is wrong path; instead: edit the on-disk file to match an OLD recorded
        # hash while shipped differs. Simpler: install, then make the manifest record
        # a hash equal to current on-disk, and change shipped is not possible here.
        # Cover the "on-disk == recorded, != shipped" branch by tampering the file to
        # the shipped bytes but recording a different content first.
        installer.install(["claude"])
        target = _skill_target(temp_home)
        # Rewrite on disk to a known content AND set the manifest hash to match it,
        # so it reads as unmodified-by-user but behind the shipped content.
        import hashlib

        from klyreon.assets.manifest import ManifestEntry, load_manifest, save_manifest

        target.write_text("old shipped content\n", encoding="utf-8")
        m = load_manifest()
        old_hash = hashlib.sha256(b"old shipped content\n").hexdigest()
        m.upsert(
            ManifestEntry("asset", "claude", str(target), old_hash, "0.0.1", "t"),
        )
        save_manifest(m)

        report = installer.install(["claude"])
        assert str(target) in report.written
        assert not report.displaced, "an unmodified-but-stale file is refreshed without a backup"
        assert target.read_bytes() == _shipped_bytes()


class TestRefresh:
    def test_refresh_reinstalls_manifest_operators(self, temp_home: Path) -> None:
        installer.install(["claude"])
        target = _skill_target(temp_home)
        target.write_text("drifted\n", encoding="utf-8")
        report = installer.refresh()
        assert str(target) in report.written
        assert target.read_bytes() == _shipped_bytes()

    def test_refresh_with_empty_manifest_does_nothing(self, temp_home: Path) -> None:
        report = installer.refresh()
        assert not report.written
        assert not report.current
        assert not report.displaced


class TestStatus:
    def test_status_current_file(self, temp_home: Path) -> None:
        installer.install(["claude"])
        statuses = installer.status()
        assert len(statuses) == 1
        s = statuses[0]
        assert s.operator == "claude"
        assert s.present
        assert s.hash_matches
        assert not s.behind_cli

    def test_status_flags_drifted_hash(self, temp_home: Path) -> None:
        installer.install(["claude"])
        _skill_target(temp_home).write_text("edited\n", encoding="utf-8")
        s = installer.status()[0]
        assert s.present
        assert not s.hash_matches

    def test_status_flags_behind_cli(self, temp_home: Path) -> None:
        installer.install(["claude"])
        target = _skill_target(temp_home)
        from klyreon.assets.manifest import ManifestEntry, load_manifest, save_manifest

        m = load_manifest()
        entry = m.entry_for_path(str(target))
        assert entry is not None
        m.upsert(
            ManifestEntry("asset", "claude", str(target), entry.sha256, "0.0.1", entry.installed_at),
        )
        save_manifest(m)
        s = installer.status()[0]
        assert s.behind_cli, "a recorded version below __version__ must flag behind_cli"


class TestUninstall:
    def test_uninstall_removes_untouched_file_and_empty_dirs(self, temp_home: Path) -> None:
        installer.install(["claude"])
        target = _skill_target(temp_home)
        assert target.is_file()
        report = installer.uninstall(["claude"])
        assert str(target) in report.removed
        assert not report.kept
        assert not target.exists()
        # Empty dirs klyreon created are gone (skills/klyreon, skills).
        assert not (temp_home / ".claude" / "skills" / "klyreon").exists()
        assert not (temp_home / ".claude" / "skills").exists()
        # Manifest entry dropped.
        assert load_manifest().entries == []

    def test_uninstall_keeps_edited_file(self, temp_home: Path) -> None:
        installer.install(["claude"])
        target = _skill_target(temp_home)
        target.write_text("my edits survive\n", encoding="utf-8")
        report = installer.uninstall(["claude"])
        assert not report.removed
        assert len(report.kept) == 1
        kept_path, reason = report.kept[0]
        assert kept_path == str(target)
        assert "edited" in reason
        assert target.read_text(encoding="utf-8") == "my edits survive\n", "a human edit is never reverted"
        # Entry dropped either way.
        assert load_manifest().entries == []

    def test_uninstall_unknown_operator_raises(self, temp_home: Path) -> None:
        from klyreon.assets.registry import UnknownOperatorError

        with pytest.raises(UnknownOperatorError):
            installer.uninstall(["emacs"])

    def test_uninstall_leaves_nonempty_dir(self, temp_home: Path) -> None:
        installer.install(["claude"])
        target = _skill_target(temp_home)
        # Drop an unrelated user file beside the installed one.
        sibling = target.parent / "USER_NOTES.md"
        sibling.write_text("keep me\n", encoding="utf-8")
        installer.uninstall(["claude"])
        assert not target.exists()
        assert sibling.exists(), "a directory holding user files must not be removed"
        assert resolve_target("claude").exists()
