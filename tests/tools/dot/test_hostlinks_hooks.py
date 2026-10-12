from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from dot.hostlinks.hooks import HOOK_NAMES, HOOK_SCRIPT, install_hooks

NOT_FOUND_LINE = "dot hook: 'dot' not found, host links not refreshed"
posix_only = pytest.mark.skipif(os.name == "nt", reason="file modes and symlinks are POSIX-only")


class TestHookConstants:
    def test_hook_names_are_checkout_merge_rewrite_in_order(self) -> None:
        assert HOOK_NAMES == ("post-checkout", "post-merge", "post-rewrite")

    def test_script_starts_with_python_shebang(self) -> None:
        assert HOOK_SCRIPT.startswith("#!/usr/bin/env python3\n")

    def test_script_ends_with_single_newline_after_exit_zero(self) -> None:
        assert HOOK_SCRIPT.endswith("sys.exit(0)\n")
        assert not HOOK_SCRIPT.endswith("sys.exit(0)\n\n")

    def test_script_disables_auto_update_in_child_env(self) -> None:
        assert '"BUVIS_AUTO_UPDATE": "false"' in HOOK_SCRIPT

    def test_script_runs_dot_materialize_hook(self) -> None:
        assert '[dot, "materialize", "--hook"]' in HOOK_SCRIPT


class TestInstallHooksFresh:
    def test_creates_missing_hooks_dir(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "a" / "b" / "hooks"

        install_hooks(hooks_dir)

        assert hooks_dir.is_dir()

    def test_writes_script_content_for_every_hook(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"

        install_hooks(hooks_dir)

        for name in HOOK_NAMES:
            assert (hooks_dir / name).read_text(encoding="utf-8") == HOOK_SCRIPT

    def test_installs_only_the_three_hooks(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"

        install_hooks(hooks_dir)

        assert sorted(p.name for p in hooks_dir.iterdir()) == sorted(HOOK_NAMES)

    @posix_only
    def test_marks_every_hook_mode_0755(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"

        install_hooks(hooks_dir)

        for name in HOOK_NAMES:
            assert stat.S_IMODE((hooks_dir / name).stat().st_mode) == 0o755

    def test_returns_installed_lines_in_hook_order(self, tmp_path: Path) -> None:
        lines = install_hooks(tmp_path / "hooks")

        assert lines == [
            "installed hook post-checkout",
            "installed hook post-merge",
            "installed hook post-rewrite",
        ]

    def test_works_when_hooks_dir_already_exists_and_is_empty(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        lines = install_hooks(hooks_dir)

        assert len(lines) == 3
        assert (hooks_dir / "post-merge").read_text(encoding="utf-8") == HOOK_SCRIPT


class TestInstallHooksExisting:
    def test_leaves_differing_hook_byte_identical_and_installs_the_rest(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        custom = b"#!/bin/sh\necho custom\r\n\xff"
        (hooks_dir / "post-merge").write_bytes(custom)

        lines = install_hooks(hooks_dir)

        assert (hooks_dir / "post-merge").read_bytes() == custom
        assert lines == ["installed hook post-checkout", "installed hook post-rewrite"]
        assert (hooks_dir / "post-checkout").read_text(encoding="utf-8") == HOOK_SCRIPT
        assert (hooks_dir / "post-rewrite").read_text(encoding="utf-8") == HOOK_SCRIPT

    @posix_only
    def test_does_not_change_mode_of_existing_hook(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        existing = hooks_dir / "post-checkout"
        existing.write_bytes(b"custom")
        existing.chmod(0o600)

        install_hooks(hooks_dir)

        assert stat.S_IMODE(existing.stat().st_mode) == 0o600

    @posix_only
    def test_leaves_dangling_symlink_alone(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        link = hooks_dir / "post-rewrite"
        link.symlink_to(tmp_path / "missing-target")

        lines = install_hooks(hooks_dir)

        assert link.is_symlink()
        assert os.readlink(link) == str(tmp_path / "missing-target")
        assert not (tmp_path / "missing-target").exists()
        assert lines == ["installed hook post-checkout", "installed hook post-merge"]

    def test_second_call_returns_nothing(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        install_hooks(hooks_dir)

        assert install_hooks(hooks_dir) == []

    def test_second_call_keeps_installed_content(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        install_hooks(hooks_dir)

        install_hooks(hooks_dir)

        for name in HOOK_NAMES:
            assert (hooks_dir / name).read_text(encoding="utf-8") == HOOK_SCRIPT


class TestInstallHooksErrors:
    def test_propagates_oserror_when_hooks_dir_is_a_file(self, tmp_path: Path) -> None:
        blocker = tmp_path / "hooks"
        blocker.write_text("not a dir", encoding="utf-8")

        with pytest.raises(OSError):
            install_hooks(blocker)


class TestInstalledHookExecution:
    def test_exits_zero_and_reports_when_dot_is_not_on_path(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        install_hooks(hooks_dir)

        for name in HOOK_NAMES:
            result = subprocess.run(
                [sys.executable, str(hooks_dir / name)],
                env={**os.environ, "PATH": str(empty_dir)},
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == 0
            assert NOT_FOUND_LINE in result.stderr
