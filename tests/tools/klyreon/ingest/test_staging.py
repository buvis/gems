"""Phase 1: atomic staging and apply with byte-exact rollback."""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.run import staging as staging_mod
from klyreon.run.staging import Staging, StagingError
from klyreon.vault.git import GitIdentity

pytestmark = pytest.mark.klyreon

IDENTITY = GitIdentity(name="klyreon", email="klyreon@localhost")


@pytest.fixture
def xdg_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


class TestApplyHappy:
    def test_apply_writes_moves_commits_and_cleans_staging(self, git_vault: Path, xdg_state: None) -> None:
        import subprocess

        root = git_vault
        src = root / "sources" / "2026-05" / "article-x.md"
        src.write_text("source body\n")
        # In a real vault the inbox source is already git-tracked; commit it so
        # the move's deletion is stageable.
        subprocess.run(["git", "-C", str(root), "add", "sources/2026-05/article-x.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "add source"], check=True)

        st = Staging(run_id="run1", source="article-x")
        st.stage("wiki/notes/20260501100000.md", "---\nid: z\n---\n# z\n")
        st.stage_source_move("sources/2026-05/article-x.md", "sources/archive/2026-05/article-x.md")
        sha = st.apply(root, IDENTITY, "ingest article-x")

        assert sha
        assert (root / "wiki" / "notes" / "20260501100000.md").is_file()
        assert (root / "sources" / "archive" / "2026-05" / "article-x.md").is_file()
        assert not (root / "sources" / "2026-05" / "article-x.md").exists()
        # Staging directory is gone (scratch, Q16).
        assert not st.dir.exists()


class TestRollback:
    def test_exception_mid_apply_leaves_vault_byte_identical(
        self,
        git_vault: Path,
        xdg_state: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = git_vault
        inbox = root / "sources" / "2026-05" / "article-x.md"
        inbox.write_text("source body\n")

        before = _snapshot(root)

        def boom(*_a: object, **_k: object) -> str:
            msg = "simulated commit failure"
            raise RuntimeError(msg)

        monkeypatch.setattr(staging_mod, "commit", boom)

        st = Staging(run_id="run1", source="article-x")
        st.stage("wiki/notes/20260501100000.md", "---\nid: z\n---\n# z\n")
        st.stage_source_move("sources/2026-05/article-x.md", "sources/archive/2026-05/article-x.md")

        with pytest.raises(StagingError):
            st.apply(root, IDENTITY, "ingest article-x")

        assert _snapshot(root) == before
        assert inbox.is_file()
        assert not (root / "sources" / "archive" / "2026-05" / "article-x.md").exists()
        assert not (root / "wiki" / "notes" / "20260501100000.md").exists()
        assert not st.dir.exists()

    def test_overwrite_is_restored_on_rollback(
        self,
        git_vault: Path,
        xdg_state: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = git_vault
        existing = root / "wiki" / "notes" / "20260101000000.md"
        existing.write_text("ORIGINAL CONTENT\n")

        def boom(*_a: object, **_k: object) -> str:
            msg = "boom"
            raise RuntimeError(msg)

        monkeypatch.setattr(staging_mod, "commit", boom)
        st = Staging(run_id="run2", source="s")
        st.stage("wiki/notes/20260101000000.md", "OVERWRITTEN CONTENT\n")
        with pytest.raises(StagingError):
            st.apply(root, IDENTITY, "x")
        assert existing.read_text() == "ORIGINAL CONTENT\n"


def _snapshot(root: Path) -> dict[str, bytes]:
    """Map vault-relative path -> bytes for every file under root, excluding .git."""
    out: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.relative_to(root).parts:
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out
