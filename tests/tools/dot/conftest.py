from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter


@pytest.fixture
def dotfiles_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "dotfiles"
    root.mkdir()
    monkeypatch.setenv("DOTFILES_ROOT", str(root))
    return root


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
