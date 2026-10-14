"""Two-host real-git tests for pull rescue.

These tests create a realistic two-host scenario:
- A bare origin repo
- Host A and B as clones with work-trees
- Host A localizes a tracked file and pushes
- Host B pulls and should see rescue behavior
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter
from dot.commands.pull.pull import CommandPull
from dot.hostlinks.rescue import Resolution


def _git(buvis_dir: Path, work_tree: Path) -> list[str]:
    """Return the base argv for a bare dotfiles git invocation."""
    return [
        "git",
        f"--git-dir={buvis_dir}",
        f"--work-tree={work_tree}",
    ]


def _run(argv: list[str], cwd: Path | None = None, check: bool = True) -> str:
    """Run a git command via argv (no shell) and return stdout."""
    result = subprocess.run(  # fixed git argv, no shell, test-only
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )
    return result.stdout


def _setup_bare_host(origin: Path, host_path: Path) -> Path:
    """Clone origin to a host path and set up as a bare dotfiles repo."""
    _run(["git", "clone", str(origin), str(host_path)])

    # Convert to bare dotfiles structure: move .git to .buvis
    buvis_dir = host_path / ".buvis"
    (host_path / ".git").rename(buvis_dir)

    git = _git(buvis_dir, host_path)
    _run([*git, "config", "user.email", "test@test.local"])
    _run([*git, "config", "user.name", "Test User"])
    _run([*git, "branch", "--set-upstream-to=origin/master", "master"])

    # Add .buvis to .gitignore (critical for bare repo setup)
    gitignore = host_path / ".gitignore"
    if gitignore.exists():
        existing = gitignore.read_text()
        gitignore_content = existing if ".buvis" in existing else existing + "\n.buvis\n"
    else:
        gitignore_content = ".buvis\n"
    gitignore.write_text(gitignore_content)

    _run([*git, "add", ".gitignore"])

    return host_path


@pytest.fixture
def two_host_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """Create a bare origin with two cloned hosts."""
    # Set git identity via environment
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test User")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@test.local")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test User")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@test.local")

    # Create bare origin
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _run(["git", "init", "--bare", str(origin)])

    # Seed initial content through a temporary clone
    init_clone = tmp_path / "init_clone"
    _run(["git", "clone", str(origin), str(init_clone)])
    _run(["git", "config", "user.email", "test@test.local"], cwd=init_clone)
    _run(["git", "config", "user.name", "Test User"], cwd=init_clone)

    (init_clone / ".gitignore").write_text(".buvis\n")
    _run(["git", "add", ".gitignore"], cwd=init_clone)

    (init_clone / ".zshrc").write_text("shared config")
    _run(["git", "add", ".zshrc"], cwd=init_clone)
    _run(["git", "commit", "-m", "Initial commit"], cwd=init_clone)
    _run(["git", "push"], cwd=init_clone)

    host_a = _setup_bare_host(origin, tmp_path / "host_a")
    host_b = _setup_bare_host(origin, tmp_path / "host_b")

    return origin, host_a, host_b


def _disable_git_secret(shell: ShellAdapter) -> None:
    """Make the shell report git-secret as unavailable (avoids reveal step)."""
    original = shell.is_command_available
    shell.is_command_available = lambda cmd: False if cmd == "git-secret" else original(cmd)


class TestTwoHostLocalizeAndPull:
    def test_two_host_localize_then_pull_rescues(self, two_host_setup: tuple[Path, Path, Path]) -> None:
        """A localizes tracked file, pushes; B has tracked copy, pulls -> B's bytes rescued.

        This tests the primary PRD scenario: B has the original tracked file content.
        When A localizes and pushes, the deletion would remove B's copy. The rescue
        preserves B's bytes at the source location.
        """
        _origin, host_a, host_b = two_host_setup

        # Host B has the original tracked .zshrc (same as what was committed)
        assert (host_b / ".zshrc").exists()
        assert (host_b / ".zshrc").read_text() == "shared config"

        # Host A localizes .zshrc
        from dot.commands.localize.localize import CommandLocalize

        shell_a = ShellAdapter(suppress_logging=True)
        localize_result = CommandLocalize(
            shell=shell_a,
            dotfiles_root=str(host_a),
            path=".zshrc",
        ).execute()
        assert localize_result.success, localize_result.error

        # Host A commits and pushes (localize already staged the manifest and deletion)
        git_a = _git(host_a / ".buvis", host_a)
        _run([*git_a, "commit", "-m", "Localize .zshrc"])
        _run([*git_a, "push"])

        # Host B pulls - treat git-secret as unavailable to avoid the reveal step
        shell_b = ShellAdapter(suppress_logging=True)
        _disable_git_secret(shell_b)

        pull_result = CommandPull(shell=shell_b, dotfiles_root=str(host_b)).execute()
        assert pull_result.success, pull_result.error

        # Host B's original bytes should be at the source location
        assert (host_b / ".local/.zshrc").read_text() == "shared config"

        # Target should be a link pointing to source
        assert (host_b / ".zshrc").is_symlink()

    def test_two_host_collision_fails_noninteractive(self, two_host_setup: tuple[Path, Path, Path]) -> None:
        """A localizes, B also has a different source file -> noninteractive failure.

        This tests the collision scenario where B has BOTH a target file AND a
        source file at the host-link's source location with different content.
        """
        _origin, host_a, host_b = two_host_setup

        # Host B has the original tracked .zshrc
        assert (host_b / ".zshrc").read_text() == "shared config"

        # Host B also has a source file with different content (prior local changes)
        (host_b / ".local").mkdir()
        (host_b / ".local/.zshrc").write_text("host B source bytes")

        # Host A localizes .zshrc
        from dot.commands.localize.localize import CommandLocalize

        shell_a = ShellAdapter(suppress_logging=True)
        localize_result = CommandLocalize(
            shell=shell_a,
            dotfiles_root=str(host_a),
            path=".zshrc",
        ).execute()
        assert localize_result.success, localize_result.error

        # Host A commits and pushes
        git_a = _git(host_a / ".buvis", host_a)
        _run([*git_a, "commit", "-m", "Localize .zshrc"])
        _run([*git_a, "push"])

        # Get host B's HEAD before pull
        git_b = _git(host_b / ".buvis", host_b)
        head_before = _run([*git_b, "rev-parse", "HEAD"]).strip()

        # Host B pulls (noninteractive, no resolutions)
        shell_b = ShellAdapter(suppress_logging=True)
        _disable_git_secret(shell_b)

        pull_result = CommandPull(shell=shell_b, dotfiles_root=str(host_b)).execute()

        # Should fail with unresolved collision
        assert not pull_result.success
        assert "unresolved host-link collision" in pull_result.error

        # Host B's HEAD should be unchanged
        head_after = _run([*git_b, "rev-parse", "HEAD"]).strip()
        assert head_before == head_after

        # Files should be unchanged - original tracked content and source
        assert (host_b / ".zshrc").read_text() == "shared config"
        assert (host_b / ".local/.zshrc").read_text() == "host B source bytes"

    def test_two_host_collision_with_resolution_succeeds(self, two_host_setup: tuple[Path, Path, Path]) -> None:
        """A localizes, B has collision, provides resolution -> succeeds."""
        _origin, host_a, host_b = two_host_setup

        # Host B has the original tracked .zshrc
        assert (host_b / ".zshrc").read_text() == "shared config"

        # Host B also has a source file with different content
        (host_b / ".local").mkdir()
        (host_b / ".local/.zshrc").write_text("host B source bytes")

        # Host A localizes .zshrc
        from dot.commands.localize.localize import CommandLocalize

        shell_a = ShellAdapter(suppress_logging=True)
        localize_result = CommandLocalize(
            shell=shell_a,
            dotfiles_root=str(host_a),
            path=".zshrc",
        ).execute()
        assert localize_result.success, localize_result.error

        # Host A commits and pushes
        git_a = _git(host_a / ".buvis", host_a)
        _run([*git_a, "commit", "-m", "Localize .zshrc"])
        _run([*git_a, "push"])

        # Host B pulls with KEEP_SOURCE resolution
        shell_b = ShellAdapter(suppress_logging=True)
        _disable_git_secret(shell_b)

        pull_result = CommandPull(shell=shell_b, dotfiles_root=str(host_b)).execute(
            resolutions={".zshrc": Resolution.KEEP_SOURCE}
        )
        assert pull_result.success, pull_result.error

        # Source should still have B's original source bytes
        assert (host_b / ".local/.zshrc").read_text() == "host B source bytes"

        # Target (shared config) should be backed up
        backup_files = list((host_b / ".local").glob(".zshrc.dot-*"))
        assert len(backup_files) == 1
        assert backup_files[0].read_text() == "shared config"

        # Target should be a link
        assert (host_b / ".zshrc").is_symlink()
