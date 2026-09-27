from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from backup.shared.bkpignore import (
    BKPIGNORE_FILENAME,
    ExcludeState,
    state_for_directory,
)
from backup.step_result import ArchiveMeta, StepResult

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

__all__ = ["TarArchive", "WalkResult"]

_ARCHIVE_MODE = 0o600
_ENGINE_PYTHON = "python-tarfile"
_ENGINE_SYSTEM_TAR = "system-tar"


class WalkResult:
    """The outcome of walking + filtering a source tree, before any archive.

    ``files`` are the surviving entries as absolute paths in walk order —
    regular files first, then symlinks (each archived as the link itself, not
    followed, matching the former tar backup); ``file_count`` and ``total_bytes``
    summarise them (a symlink contributes 0 input bytes); ``applied`` lists the
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
        return {"source": "", "out": "", "engine": _ENGINE_PYTHON}

    def run(self: TarArchive, **kwargs: object) -> Iterator[StepResult]:
        label = _require_str(kwargs, "label", default="tar-archive")
        source_raw = _require_str(kwargs, "source")
        out_raw = _require_str(kwargs, "out")
        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON
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

        if engine not in (_ENGINE_PYTHON, _ENGINE_SYSTEM_TAR):
            yield StepResult(
                label,
                success=False,
                message=f"unknown engine '{engine}'; expected {_ENGINE_PYTHON} or {_ENGINE_SYSTEM_TAR}",
            )
            return

        if not source.is_dir():
            yield StepResult(label, success=False, message=f"source not found: {source}")
            return

        containment = _reject_out_inside_source(label, source, out)
        if containment is not None:
            yield containment
            return

        base_state = ExcludeState(base_excludes=frozenset(excludes))
        walk = _walk_tree(source, base_state)

        if dry_run:
            yield self._dry_run_result(label, out, walk)
            return

        yield self._archive_result(label, source, out, walk, engine)

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
    def _archive_result(label: str, source: Path, out: Path, walk: WalkResult, engine: str) -> StepResult:
        out.parent.mkdir(parents=True, exist_ok=True)
        note = ""
        if engine == _ENGINE_SYSTEM_TAR:
            fallback = _write_archive_system_tar(out, source, walk.files)
            if fallback is not None:
                _write_archive(out, source, walk.files)
                note = f" (system-tar unavailable: {fallback}; used python engine)"
        else:
            _write_archive(out, source, walk.files)
        size = out.stat().st_size
        return StepResult(
            label,
            success=True,
            message=(
                f"archived {walk.file_count} files -> {out} ({walk.total_bytes} bytes in, {size} bytes on disk){note}"
            ),
            archive=ArchiveMeta(out_path=str(out), file_count=walk.file_count, total_bytes=walk.total_bytes),
        )


def _reject_out_inside_source(label: str, source: Path, out: Path) -> StepResult | None:
    """Reject an ``out`` path that lands inside the ``source`` tree.

    An ``out`` under ``source`` makes each run re-archive the previous run's
    archive (unbounded recursive growth). ``out`` may not exist yet, so its
    PARENT is resolved (which does exist — a stamp only expands the basename) and
    the name rejoined, giving a real absolute path to test for containment
    against the resolved source. Returns a failed :class:`StepResult` when ``out``
    is inside ``source`` (the caller yields it and returns before walking),
    otherwise ``None``.
    """
    source_resolved = source.resolve()
    out_resolved = out.parent.resolve() / out.name
    if out_resolved == source_resolved or source_resolved in out_resolved.parents:
        return StepResult(
            label,
            success=False,
            message=(f"out path {out} is inside source {source}; choose an out path outside the backup source"),
        )
    return None


def _walk_tree(source: Path, base_state: ExcludeState) -> WalkResult:
    """Walk ``source`` top-down, applying global excludes + path-scoped ``.bkpignore``.

    The exclude state at each directory is the ancestors' state layered with
    that directory's own ``.bkpignore`` (if any). Excluded directories are
    pruned from further descent; surviving regular files are collected.
    """
    files: list[Path] = []
    symlinks: list[Path] = []
    total_bytes = 0
    states: dict[str, ExcludeState] = {str(source): state_for_directory(source, base_state)}

    for dirpath, dirnames, filenames in os.walk(source, onerror=_raise_walk_error):
        state = states[dirpath]

        kept_dirs: list[str] = []
        for dirname in dirnames:
            child = os.path.join(dirpath, dirname)
            relpath = os.path.relpath(child, source).replace(os.sep, "/")
            if state.is_excluded(dirname, relpath):
                continue
            # A directory symlink: os.walk (followlinks=False) will not descend
            # it, and we must NOT read <link>/.bkpignore (it may point outside
            # the source tree) — so it stays out of kept_dirs. But the link
            # ITSELF is archived as a non-recursive symlink member, so restoring
            # preserves it (the former tar backup kept symlinks). tarfile /
            # system tar store a symlink as a link without following it.
            if os.path.islink(child):
                symlinks.append(Path(child))
                continue
            states[child] = state_for_directory(Path(child), state)
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            if filename == BKPIGNORE_FILENAME:
                continue
            file_path = Path(dirpath) / filename
            relpath = os.path.relpath(file_path, source).replace(os.sep, "/")
            if state.is_excluded(filename, relpath):
                continue
            # Archive a symlink as the link itself (not its target), matching the
            # former tar backup — but never stat() it (that follows the link and
            # a broken link would raise); a link contributes 0 input bytes.
            if file_path.is_symlink():
                symlinks.append(file_path)
                continue
            if not file_path.is_file():
                continue
            files.append(file_path)
            # No suppression: a file we selected but cannot stat is a real error
            # for an archiver, not a 0-byte undercount. The runner turns the
            # propagated OSError into a failed step.
            total_bytes += file_path.stat().st_size

    return WalkResult(
        files=[*files, *symlinks],
        total_bytes=total_bytes,
        applied=_collect_applied(states),
    )


def _raise_walk_error(error: OSError) -> None:
    """``os.walk`` ``onerror`` callback that re-raises a directory-scan error.

    Without it ``os.walk`` silently swallows an unreadable subtree, yielding a
    partial archive reported as success. Re-raising lets the runner's
    ``except Exception -> StepResult(success=False)`` turn it into a failed step.
    """
    raise error


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


def _write_archive_system_tar(out: Path, source: Path, files: Iterable[Path]) -> str | None:
    """Archive ``files`` via system ``tar --null -T -``, atomically, ``chmod 600``.

    Python still owns selection: ``files`` is the exact include list the walk
    produced (so ``.bkpignore`` path-scoping is preserved). The paths, relative
    to ``source.parent``, are joined with NUL bytes and streamed to
    ``tar -C <source.parent> --null -T - -czf <tmp>`` on stdin. NUL delimiting
    (both GNU tar and macOS bsdtar support ``--null``) means a filename
    containing a newline can never split into an extra ``-T`` line and inject an
    outside/absolute path. The gzip output lands in a sibling temp file, is
    ``fsync``ed and ``chmod 600``ed, then ``os.replace``d into ``out``,
    preserving the Python engine's atomicity and durability guarantee.

    Returns:
        ``None`` when the archive was written successfully; otherwise a short
        reason string so the caller can fall back to the Python engine and note
        why. A partial temp archive is always cleaned up.
    """
    tar_bin = shutil.which("tar")
    if tar_bin is None:
        return "tar not found on PATH"

    arcbase = source.parent
    fd, tmp_name = tempfile.mkstemp(prefix=out.name + ".", suffix=".tmp", dir=str(out.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    # NUL-delimited list on stdin: a NUL cannot occur in a POSIX path component,
    # so no filename (even one containing a newline) can inject an extra entry.
    filelist = b"".join(os.fsencode(file_path.relative_to(arcbase)) + b"\0" for file_path in files)
    try:
        # bsdtar (macOS) otherwise stores AppleDouble (``._name``) metadata
        # members that the Python engine never produces; COPYFILE_DISABLE
        # suppresses them and is a no-op for GNU tar on Linux.
        env = {**os.environ, "COPYFILE_DISABLE": "1"}
        completed = subprocess.run(
            [tar_bin, "-C", str(arcbase), "--null", "-czf", str(tmp_path), "-T", "-"],
            input=filelist,
            capture_output=True,
            check=False,
            env=env,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", "replace").strip().splitlines()
            detail = stderr[-1] if stderr else f"exit {completed.returncode}"
            return f"tar exited {completed.returncode}: {detail}"
        # Match the Python engine's durability: fsync the finished temp archive
        # before atomically swapping it into place.
        archive_fd = os.open(str(tmp_path), os.O_RDONLY)
        try:
            os.fsync(archive_fd)
        finally:
            os.close(archive_fd)
        os.chmod(tmp_path, _ARCHIVE_MODE)
        os.replace(tmp_path, out)
    except OSError as exc:
        return f"tar invocation failed: {exc}"
    finally:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
    return None


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
