"""Git layer and autonomy gate, on real temporary repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from klyreon.vault.git import (
    GitIdentity,
    commit,
    is_git_vault,
    is_human_authored,
    require_git_for_autonomy,
)

if TYPE_CHECKING:
    from collections.abc import Generator

KLYREON = GitIdentity(name="klyreon", email="klyreon@localhost")


def _git(root: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _git_operable(base: Path) -> bool:
    """Return True when 'git init' succeeds under ``base`` (some sandboxes deny it)."""
    probe = base / "git-probe"
    try:
        probe.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["git", "-C", str(probe), "init", "-q"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    finally:
        import shutil as _sh

        _sh.rmtree(probe, ignore_errors=True)
    return completed.returncode == 0


@pytest.fixture
def temp_repo(tmp_path: Path) -> Generator[Path, None, None]:
    import shutil
    import tempfile

    # pytest's tmp_path can live under a sandbox-restricted root where 'git init'
    # is denied (exit 128). Prefer it (CI), fall back to /tmp, else skip.
    base: Path | None = None
    for candidate in (tmp_path, Path("/tmp")):
        if _git_operable(candidate):
            base = Path(tempfile.mkdtemp(prefix="klyreon-git-", dir=str(candidate)))
            break
    if base is None:
        pytest.skip("no git-operable temp directory available in this environment")

    root = base / "vault"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Human Owner")
    _git(root, "config", "user.email", "human@example.com")
    # Test-local only: the sandbox denies ~/.gnupg, so the fixture's own human
    # seed commits cannot sign. This repo-local setting never touches global config.
    _git(root, "config", "commit.gpgsign", "false")
    try:
        yield root
    finally:
        shutil.rmtree(base, ignore_errors=True)


class TestIsGitVault:
    def test_true_in_repo(self, temp_repo: Path) -> None:
        assert is_git_vault(temp_repo) is True

    def test_false_in_plain_dir(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        assert is_git_vault(plain) is False


class TestAutonomyGate:
    def test_refuses_in_plain_dir(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        result = require_git_for_autonomy(plain)
        assert result.success is False
        assert result.error

    def test_allows_in_repo(self, temp_repo: Path) -> None:
        assert require_git_for_autonomy(temp_repo).success is True


class TestScopedCommit:
    def test_commit_two_paths_leaves_third_modified_and_unstaged(self, temp_repo: Path) -> None:
        # Seed three tracked files via an initial human commit.
        for name in ("a.md", "b.md", "c.md"):
            (temp_repo / name).write_text("initial\n")
        _git(temp_repo, "add", "-A")
        _git(temp_repo, "commit", "-q", "-m", "seed")

        # Human edits c.md but does not commit; klyreon rewrites a.md and b.md.
        (temp_repo / "a.md").write_text("klyreon a\n")
        (temp_repo / "b.md").write_text("klyreon b\n")
        (temp_repo / "c.md").write_text("human edit uncommitted\n")

        commit(temp_repo, ["a.md", "b.md"], "feat: klyreon writes a and b", KLYREON)

        status = _git(temp_repo, "status", "--porcelain").stdout
        # c.md must remain modified and unstaged ( " M c.md" ).
        assert " M c.md" in status
        # a.md and b.md are committed, so they are no longer in the worktree-dirty set.
        assert "a.md" not in status
        assert "b.md" not in status

    def test_commit_author_is_klyreon_identity(self, temp_repo: Path) -> None:
        (temp_repo / "a.md").write_text("x\n")
        sha = commit(temp_repo, ["a.md"], "feat: add a", KLYREON)
        author = _git(temp_repo, "log", "-1", "--format=%an", sha).stdout.strip()
        email = _git(temp_repo, "log", "-1", "--format=%ae", sha).stdout.strip()
        assert author == "klyreon"
        assert email == "klyreon@localhost"

    def test_global_identity_untouched(self, temp_repo: Path) -> None:
        (temp_repo / "a.md").write_text("x\n")
        commit(temp_repo, ["a.md"], "feat: add a", KLYREON)
        # The repo-local user.name set by the fixture is still the human.
        assert _git(temp_repo, "config", "user.name").stdout.strip() == "Human Owner"


class TestAuthorship:
    def test_human_authored_true_after_human_commit(self, temp_repo: Path) -> None:
        (temp_repo / "h.md").write_text("x\n")
        _git(temp_repo, "add", "h.md")
        _git(temp_repo, "commit", "-q", "-m", "human commit")  # uses fixture's Human Owner identity
        assert is_human_authored(temp_repo, "h.md", KLYREON) is True

    def test_human_authored_false_for_klyreon_only(self, temp_repo: Path) -> None:
        (temp_repo / "k.md").write_text("x\n")
        commit(temp_repo, ["k.md"], "feat: klyreon only", KLYREON)
        assert is_human_authored(temp_repo, "k.md", KLYREON) is False

    def test_untracked_path_not_human_authored(self, temp_repo: Path) -> None:
        assert is_human_authored(temp_repo, "never.md", KLYREON) is False
