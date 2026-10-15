"""Real-git tests for ``dot setup``: clone, self-heal, checkout, hook-driven relink."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter
from dot.commands.setup.setup import CommandSetup
from dot.git.service import DotGitService
from dot.hostlinks.hooks import HOOK_NAMES, HOOK_SCRIPT

pytestmark = pytest.mark.skipif(os.name == "nt", reason="exec bits, symlinks, python3 hooks are POSIX-only")


def _run(argv: list[str], cwd: Path | None = None) -> str:
    """Run a fixed git argv (no shell) and return stdout."""
    return subprocess.run(  # fixed git argv, no shell, test-only
        argv, cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _git_config(home: Path, key: str) -> str:
    return _run(["git", f"--git-dir={home}/.buvis", f"--work-tree={home}", "config", key]).strip()


def _upstream(home: Path) -> str:
    argv = ["git", f"--git-dir={home}/.buvis", f"--work-tree={home}", "rev-parse", "--abbrev-ref", "@{u}"]
    return _run(argv).strip()


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Build an origin repo and an empty home; return ``(origin, home)``."""
    for var in ("GIT_AUTHOR", "GIT_COMMITTER"):
        monkeypatch.setenv(f"{var}_NAME", "Test User")
        monkeypatch.setenv(f"{var}_EMAIL", "test@test.local")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)
    monkeypatch.delenv("GIT_CONFIG_PARAMETERS", raising=False)
    monkeypatch.delenv("BUVIS_CONFIG_DIR", raising=False)
    monkeypatch.delenv("BUVIS_CONFIG_FILE", raising=False)
    # Not resolved: the venv bin/python is a symlink and resolving leaves the venv.
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    assert shutil.which("dot"), "dot entry point missing from the venv bin; run uv sync"

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DOTFILES_ROOT", str(home))
    host_file = home / "hosts" / "h1" / "gitconfig"
    host_file.parent.mkdir(parents=True)
    host_file.write_text("[user]\n")

    origin = tmp_path / "origin"
    _run(["git", "init", "-q", "-b", "master", str(origin)])
    manifest = origin / ".config" / "buvis" / "host-links"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(".gitconfig => hosts/h1/gitconfig\n")
    for name in HOOK_NAMES:
        hook = manifest.parent / "hooks" / name
        hook.parent.mkdir(exist_ok=True)
        hook.write_text(HOOK_SCRIPT)
        hook.chmod(0o755)
    (origin / ".zshrc").write_text("shared\n")
    _run(["git", "add", "."], cwd=origin)
    _run(["git", "commit", "-qm", "init"], cwd=origin)
    return origin, home


class TestSetupRealGit:
    def test_setup_into_empty_home_sets_hooks_path_upstream_files_and_links(self, env: tuple[Path, Path]) -> None:
        origin, home = env

        result = CommandSetup(ShellAdapter(suppress_logging=True), str(home), str(origin)).execute()

        assert result.success, result.error
        assert result.info[:2] == [f"cloned {origin}", "checked out"]
        assert _git_config(home, "core.hooksPath") == f"{home}/.config/buvis/hooks"
        assert _git_config(home, "status.showUntrackedFiles") == "no"
        assert _upstream(home) == "origin/master"
        assert (home / ".zshrc").read_text() == "shared\n"
        # The first-checkout post-checkout hook may already have linked it, so assert disk state only.
        assert (home / ".gitconfig").is_symlink()
        assert (home / ".gitconfig").resolve() == (home / "hosts" / "h1" / "gitconfig").resolve()

    def test_later_checkout_fires_post_checkout_and_relinks_removed_link(self, env: tuple[Path, Path]) -> None:
        origin, home = env
        shell = ShellAdapter(suppress_logging=True)
        assert CommandSetup(shell, str(home), str(origin)).execute().success
        (home / ".gitconfig").unlink()

        service = DotGitService(shell, str(home))
        err, _out = service.shell.exe("cfg checkout -- .", service.wd)

        assert err == ""
        assert (home / ".gitconfig").is_symlink()

    def test_setup_materializes_links_and_hooks_when_origin_ships_no_hooks(self, env: tuple[Path, Path]) -> None:
        origin, home = env
        _run(["git", "rm", "-rq", ".config/buvis/hooks"], cwd=origin)
        _run(["git", "commit", "-qm", "drop hooks"], cwd=origin)

        result = CommandSetup(ShellAdapter(suppress_logging=True), str(home), str(origin)).execute()

        # No post-checkout hook fired, so only step 7 can have made these.
        assert result.success, result.error
        assert (home / ".gitconfig").is_symlink()
        for name in HOOK_NAMES:
            assert (home / ".config" / "buvis" / "hooks" / name).is_file()

    def test_checkout_conflict_fails_and_leaves_existing_file_bytes(self, env: tuple[Path, Path]) -> None:
        origin, home = env
        (home / ".zshrc").write_bytes(b"mine\r\n\xff")

        result = CommandSetup(ShellAdapter(suppress_logging=True), str(home), str(origin)).execute()

        assert not result.success
        assert result.error is not None
        assert result.error.startswith("checkout conflicts with existing files, nothing overwritten:\n")
        assert ".zshrc" in result.error
        assert result.error.endswith("move them away, then run: dot run checkout")
        assert (home / ".zshrc").read_bytes() == b"mine\r\n\xff"
        assert not (home / ".gitconfig").exists()

    def test_checkout_refuses_to_overwrite_an_ignored_existing_file(self, env: tuple[Path, Path]) -> None:
        origin, home = env
        # Plain `git checkout` silently overwrites untracked files that are ignored.
        (home / ".gitignore").write_text(".zshrc\n")
        (home / ".zshrc").write_bytes(b"mine\n")

        result = CommandSetup(ShellAdapter(suppress_logging=True), str(home), str(origin)).execute()

        assert not result.success
        assert result.error is not None
        assert ".zshrc" in result.error
        assert (home / ".zshrc").read_bytes() == b"mine\n"
