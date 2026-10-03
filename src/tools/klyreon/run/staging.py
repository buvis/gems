"""Atomic staging and apply: a source lands entirely or not at all.

Staging lives under ``$XDG_STATE_HOME/klyreon/staging/<run-id>/<source>/``,
mirroring vault-relative paths, and is deleted at the end of the source either
way; it is scratch, never resume state (discovery Q16).

Apply order (PRD "Atomic staging and apply"): write new and edited zettels,
write MOC updates, move the source into the archive, then commit exactly those
paths with 00074's scoped :func:`commit`. Any exception during apply rolls
back: files this apply created are removed, files it overwrote are restored
byte-for-byte, and the archive move is reversed. A hard kill mid-apply can
leave uncommitted files; ``klyreon validate`` reports it and git clean fixes
it (marked below with the two-phase-commit upgrade path).
"""

# ponytail: a hard kill between the first file write and the commit can leave
# uncommitted files in the working tree. The window is milliseconds of file
# writes; validate reports it and `git checkout`/`git clean` fixes it. If this
# ever bites, the upgrade path is a two-phase commit (write a journal marker,
# apply, then clear it; recover from the marker on the next run).

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from buvis.pybase.filesystem import atomic_write_text

from klyreon.vault.git import GitIdentity, commit

__all__ = ["Staging", "StagingError", "staging_root"]


class StagingError(RuntimeError):
    """Raised when apply fails; the vault has been rolled back to its prior state."""


def staging_root() -> Path:
    """Return ``$XDG_STATE_HOME/klyreon/staging`` (honouring the env var)."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "klyreon" / "staging"


def _is_tracked(root: Path, rel: str) -> bool:
    """Return True when ``rel`` is a git-tracked path under ``root``."""
    import subprocess

    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", rel],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


@dataclass
class _Move:
    src: Path
    dst: Path


@dataclass
class Staging:
    """A per-source staging area with all-or-nothing apply.

    Call :meth:`stage` for each vault-relative file the source produces, then
    :meth:`apply` once. :meth:`apply` always cleans the staging directory; on
    any error it also rolls the vault back and raises :class:`StagingError`.
    """

    run_id: str
    source: str
    _files: dict[str, str] = field(default_factory=dict)
    _move: _Move | None = None

    @property
    def dir(self) -> Path:
        return staging_root() / self.run_id / self.source

    def stage(self, rel_path: str, content: str) -> None:
        """Stage ``content`` to be written at vault-relative ``rel_path``.

        Materialises it under the on-disk staging dir (scratch, Q16) so the set
        survives in one place until apply; :meth:`apply` reads from there.
        """
        self._files[rel_path] = content
        staged = self.dir / rel_path
        staged.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(staged, content)

    def stage_source_move(self, src_rel: str, dst_rel: str) -> None:
        """Record the inbox->archive move to apply with the rest of the set."""
        self._move = _Move(src=Path(src_rel), dst=Path(dst_rel))

    def apply(self, root: Path, identity: GitIdentity, subject: str) -> str:
        """Apply the staged set to ``root`` and commit exactly those paths.

        Returns the commit SHA. On any failure, rolls the vault back to its
        pre-apply state, cleans staging, and raises :class:`StagingError`.
        """
        created: list[Path] = []
        overwritten: dict[Path, bytes] = {}
        move_done = False
        committed_paths: list[str] = []
        try:
            for rel_path, content in self._files.items():
                abs_path = root / rel_path
                if abs_path.exists():
                    overwritten[abs_path] = abs_path.read_bytes()
                else:
                    created.append(abs_path)
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(abs_path, content)
                committed_paths.append(rel_path)

            if self._move is not None:
                src_abs = root / self._move.src
                dst_abs = root / self._move.dst
                src_was_tracked = _is_tracked(root, self._move.src.as_posix())
                dst_abs.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_abs), str(dst_abs))
                move_done = True
                # Stage the deletion of the old path only when git knew about it;
                # a freshly dropped-in, untracked source has nothing to delete and
                # 'git add -- <gone-path>' would fail on it.
                if src_was_tracked:
                    committed_paths.append(self._move.src.as_posix())
                committed_paths.append(self._move.dst.as_posix())

            sha = commit(root, committed_paths, subject, identity)
        except Exception as exc:
            self._rollback(root, created, overwritten, move_done)
            self._cleanup()
            msg = f"apply failed for source {self.source!r}; vault rolled back: {exc}"
            raise StagingError(msg) from exc
        else:
            self._cleanup()
            return sha

    def _rollback(
        self,
        root: Path,
        created: list[Path],
        overwritten: dict[Path, bytes],
        move_done: bool,
    ) -> None:
        # Reverse the archive move first so a restored source lands in the inbox.
        if move_done and self._move is not None:
            dst_abs = root / self._move.dst
            src_abs = root / self._move.src
            if dst_abs.exists():
                src_abs.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst_abs), str(src_abs))
        for abs_path in created:
            if abs_path.exists():
                abs_path.unlink()
        for abs_path, original in overwritten.items():
            atomic_write_text(abs_path, original.decode("utf-8"))

    def _cleanup(self) -> None:
        run_dir = staging_root() / self.run_id / self.source
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
