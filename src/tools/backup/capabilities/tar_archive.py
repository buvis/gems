from __future__ import annotations

import contextlib
import os
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from backup.shared.bkpignore import BKPIGNORE_FILENAME, ExcludeState, parse_bkpignore
from backup.step_result import ArchiveMeta, StepResult

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

__all__ = ["TarArchive", "WalkResult"]

_ARCHIVE_MODE = 0o600


class WalkResult:
    """The outcome of walking + filtering a source tree, before any archive.

    ``files`` are the surviving regular files as absolute paths in walk order;
    ``file_count`` and ``total_bytes`` summarise them; ``applied`` lists the
    ``.bkpignore`` rules that fired anywhere in the tree (for dry-run reporting).
    """

    def __init__(
        self: WalkResult,
        files: list[Path],
        total_bytes: int,
        applied: list[str],
    ) -> None:
        self.files = files
        self.total_bytes = total_bytes
        self.applied = applied

    @property
    def file_count(self: WalkResult) -> int:
        return len(self.files)


class TarArchive:
    """Tar a source tree into a compressed, ``chmod 600``, atomically-written archive.

    File selection is owned here: it :func:`os.walk`s ``source`` top-down,
    layering each directory's ``.bkpignore`` rules onto the exclude state
    inherited from its ancestors (so ``!target`` un-ignores are path-scoped to
    the file's own subtree), and adds surviving files to a
    ``tarfile.open(mode="w:gz")``. The archive is streamed to a sibling temp
    file, ``fsync``ed, ``chmod 600``ed, then ``os.replace``d into ``out`` — so a
    crash or ENOSPC never leaves a partial ``.tar.gz`` at the final path.
    """

    @property
    def inputs(self: TarArchive) -> Mapping[str, object]:
        return {"source": "", "out": ""}

    def run(self: TarArchive, **kwargs: object) -> Iterator[StepResult]:
        label = _require_str(kwargs, "label", default="tar-archive")
        source_raw = _require_str(kwargs, "source")
        out_raw = _require_str(kwargs, "out")
        excludes = _as_str_tuple(kwargs.get("excludes", ()))
        dry_run = bool(kwargs.get("dry_run", False))

        if not source_raw:
            yield StepResult(label, success=False, message="no source configured")
            return
        if not out_raw:
            yield StepResult(label, success=False, message="no out path configured")
            return

        source = Path(source_raw).expanduser()
        out = Path(_expand_stamp(out_raw)).expanduser()

        if not source.is_dir():
            yield StepResult(label, success=False, message=f"source not found: {source}")
            return

        base_state = ExcludeState(excludes=frozenset(excludes))
        walk = _walk_tree(source, base_state)

        if dry_run:
            yield self._dry_run_result(label, out, walk)
            return

        yield self._archive_result(label, source, out, walk)

    @staticmethod
    def _dry_run_result(label: str, out: Path, walk: WalkResult) -> StepResult:
        applied = ", ".join(walk.applied) if walk.applied else "none"
        message = (
            f"would archive {walk.file_count} files ({walk.total_bytes} bytes) "
            f"-> {out}; .bkpignore rules applied: {applied}"
        )
        return StepResult(
            label,
            success=True,
            message=message,
            archive=ArchiveMeta(out_path=str(out), file_count=walk.file_count, total_bytes=walk.total_bytes),
        )

    @staticmethod
    def _archive_result(label: str, source: Path, out: Path, walk: WalkResult) -> StepResult:
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_archive(out, source, walk.files)
        size = out.stat().st_size
        return StepResult(
            label,
            success=True,
            message=f"archived {walk.file_count} files -> {out} ({size} bytes)",
            archive=ArchiveMeta(out_path=str(out), file_count=walk.file_count, total_bytes=size),
        )


def _walk_tree(source: Path, base_state: ExcludeState) -> WalkResult:
    """Walk ``source`` top-down, applying global excludes + path-scoped ``.bkpignore``.

    The exclude state at each directory is the ancestors' state layered with
    that directory's own ``.bkpignore`` (if any). Excluded directories are
    pruned from further descent; surviving regular files are collected.
    """
    files: list[Path] = []
    total_bytes = 0
    states: dict[str, ExcludeState] = {str(source): _state_for(source, base_state)}

    for dirpath, dirnames, filenames in os.walk(source):
        state = states[dirpath]

        kept_dirs: list[str] = []
        for dirname in dirnames:
            child = os.path.join(dirpath, dirname)
            relpath = os.path.relpath(child, source).replace(os.sep, "/")
            if state.is_excluded(dirname, relpath):
                continue
            states[child] = _state_for(Path(child), state)
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            if filename == BKPIGNORE_FILENAME:
                continue
            file_path = Path(dirpath) / filename
            relpath = os.path.relpath(file_path, source).replace(os.sep, "/")
            if state.is_excluded(filename, relpath):
                continue
            if not file_path.is_file() or file_path.is_symlink():
                continue
            files.append(file_path)
            with contextlib.suppress(OSError):
                total_bytes += file_path.stat().st_size

    return WalkResult(files=files, total_bytes=total_bytes, applied=_collect_applied(states))


def _state_for(directory: Path, parent_state: ExcludeState) -> ExcludeState:
    """Return the exclude state for ``directory`` — parent state plus its ``.bkpignore``."""
    bkpignore = directory / BKPIGNORE_FILENAME
    if bkpignore.is_file():
        rules = parse_bkpignore(bkpignore.read_text(encoding="utf-8"))
        return parent_state.layer(rules)
    return parent_state


def _collect_applied(states: dict[str, ExcludeState]) -> list[str]:
    """Gather every distinct ``.bkpignore`` rule that fired anywhere in the tree."""
    seen: list[str] = []
    for state in states.values():
        for rule in state.applied:
            if rule not in seen:
                seen.append(rule)
    return seen


def _write_archive(out: Path, source: Path, files: Iterable[Path]) -> None:
    """Stream a ``w:gz`` tarball of ``files`` to ``out`` atomically, ``chmod 600``.

    Replicates ``pybase.filesystem.atomic_write``'s tempfile + fsync +
    ``os.replace`` guarantee, but streams tar output straight into the temp file
    (a large tarball must never be built in memory, which the byte-oriented
    ``atomic_write_bytes`` would require). Archive names are stored relative to
    ``source``'s parent, so entries are prefixed with ``source.name`` — matching
    the wrapped script's ``-C dirname basename`` layout.
    """
    arcbase = source.parent
    fd, tmp_name = tempfile.mkstemp(prefix=out.name + ".", suffix=".tmp", dir=str(out.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as raw:
            os.fchmod(fd, _ARCHIVE_MODE)
            with tarfile.open(fileobj=raw, mode="w:gz") as tar:
                for file_path in files:
                    arcname = file_path.relative_to(arcbase)
                    tar.add(str(file_path), arcname=str(arcname), recursive=False)
            raw.flush()
            os.fsync(raw.fileno())
        os.replace(tmp_path, out)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


def _require_str(kwargs: Mapping[str, object], key: str, *, default: str = "") -> str:
    value = kwargs.get(key, default)
    return value if isinstance(value, str) else default


def _expand_stamp(pattern: str) -> str:
    """Expand ``strftime`` codes in an ``out`` pattern against the current time.

    A pattern like ``git-src-%Y%m%d-%H%M%S.tar.gz`` becomes a timestamped name
    at archive time, reproducing the wrapped script's ``date +%Y%m%d-%H%M%S``
    behaviour. A pattern with no ``%`` codes is returned unchanged.
    """
    if "%" not in pattern:
        return pattern
    return datetime.now().strftime(pattern)


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()
