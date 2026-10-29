from __future__ import annotations

import contextlib
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from backup.shared.bkpignore import (
    BKPIGNORE_FILENAME,
    ExcludeState,
    state_for_directory,
)
from backup.step_result import ArchiveMeta, PlanEntry, StepResult

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

__all__ = ["TarArchive", "WalkResult"]

_ARCHIVE_MODE = 0o600
_ENGINE_PYTHON = "python-tarfile"
_ENGINE_SYSTEM_TAR = "system-tar"


class WalkResult:
    """The outcome of walking + filtering a source tree, before any archive.

    ``files`` is the ordered list of archive MEMBERS as absolute paths:
    surviving directories first (parent-first, so a restore recreates the tree
    including empty dirs), then regular files, then symlinks (each archived as
    the link itself, not followed, matching the former tar backup). ``file_count``
    counts only the regular files (not dirs or symlinks) and ``total_bytes`` sums
    their input sizes (a symlink/dir contributes 0). ``applied`` lists the
    ``.bkpignore`` rules that fired anywhere in the tree (for dry-run reporting).
    """

    def __init__(
        self: WalkResult,
        files: list[Path],
        total_bytes: int,
        applied: list[str],
        file_count: int,
    ) -> None:
        self.files = files
        self.total_bytes = total_bytes
        self.applied = applied
        self._file_count = file_count

    @property
    def file_count(self: WalkResult) -> int:
        return self._file_count


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
        return {"source": "", "out": "", "engine": _ENGINE_PYTHON, "items": None}

    def plan(self: TarArchive, **kwargs: object) -> PlanEntry:
        label = _require_str(kwargs, "label", default="tar-archive")
        source = Path(os.path.normpath(Path(_require_str(kwargs, "source")).expanduser()))
        out = Path(_expand_stamp(_require_str(kwargs, "out"), cast("datetime | None", kwargs.get("now")))).expanduser()
        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON)
        replaces = out.exists()
        status = "run"
        reason = ""

        if engine not in (_ENGINE_PYTHON, _ENGINE_SYSTEM_TAR):
            status = "fail"
            reason = f"unknown engine '{engine}'; expected {_ENGINE_PYTHON} or {_ENGINE_SYSTEM_TAR}"
        elif not source.is_dir():
            missing = not source.exists()
            status = "skip" if missing else "fail"
            reason = f"{'source not found' if missing else 'source is not a directory'}: {source}"
        else:
            containment = _reject_out_inside_source(label, source, out)
            if containment is not None:
                status = "fail"
                reason = containment.message
            elif "items" in kwargs:
                try:
                    selected = _normalize_items(source, _as_str_tuple(kwargs["items"]))
                except ValueError as exc:
                    status = "fail"
                    reason = str(exc)
                else:
                    if not any(os.path.lexists(source / item) for item in selected):
                        status = "skip"
                        reason = "no selected items to archive"

        return PlanEntry(label, str(source), str(out), status, reason, replaces)

    def run(self: TarArchive, **kwargs: object) -> Iterator[StepResult]:
        label = _require_str(kwargs, "label", default="tar-archive")
        source_raw = _require_str(kwargs, "source")
        out_raw = _require_str(kwargs, "out")
        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON
        excludes = _as_str_tuple(kwargs.get("excludes", ()))
        dry_run = bool(kwargs.get("dry_run", False))

        if not source_raw or not out_raw:
            message = "no source configured" if not source_raw else "no out path configured"
            yield StepResult(label, success=False, message=message)
            return

        # Normalize `.`/`..` LEXICALLY (os.path.normpath, not resolve()) before
        # walking: a source like `parent/child/..` would otherwise be walked as
        # given and produce member names like `..` / `../child` (an unsafe
        # archive that also breaks the documented source-name prefix). normpath
        # collapses the segments without following symlinks, so the
        # symlink-confinement guarantee is untouched.
        source = Path(os.path.normpath(Path(source_raw).expanduser()))
        out = Path(_expand_stamp(out_raw, cast("datetime | None", kwargs.get("now")))).expanduser()

        if engine not in (_ENGINE_PYTHON, _ENGINE_SYSTEM_TAR):
            yield StepResult(
                label,
                success=False,
                message=f"unknown engine '{engine}'; expected {_ENGINE_PYTHON} or {_ENGINE_SYSTEM_TAR}",
            )
            return

        if not source.is_dir():
            missing_source = not source.exists()
            reason = "source not found" if missing_source else "source is not a directory"
            yield StepResult(label, success=missing_source, message=f"{reason}: {source}", skipped=missing_source)
            return

        containment = _reject_out_inside_source(label, source, out)
        if containment is not None:
            yield containment
            return

        yield from self._run_validated(source, out, excludes, dry_run, kwargs)

    def _run_validated(
        self: TarArchive,
        source: Path,
        out: Path,
        excludes: tuple[str, ...],
        dry_run: bool,
        kwargs: dict[str, object],
    ) -> Iterator[StepResult]:
        label = _require_str(kwargs, "label", default="tar-archive")
        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON
        base_state = ExcludeState(base_excludes=frozenset(excludes))
        missing: list[str] = []
        bundle = "items" in kwargs
        if bundle:
            try:
                selected = _normalize_items(source, _as_str_tuple(kwargs["items"]))
            except ValueError as exc:
                yield StepResult(label, success=False, message=str(exc))
                return
            walk, missing = _select_items(source, base_state, selected)
            if not walk.files:
                message = "no selected items to archive"
                if missing:
                    message += f"; missing items: {', '.join(missing)}"
                yield StepResult(label, success=True, message=message, skipped=True)
                return
        else:
            walk = _walk_tree(source, base_state)

        if dry_run:
            result = self._dry_run_result(label, out, walk)
        else:
            result = self._archive_result(label, source if bundle else source.parent, out, walk, engine)
        if missing:
            result.message += f"; missing items: {', '.join(missing)}"
        yield result

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
    def _archive_result(label: str, arcbase: Path, out: Path, walk: WalkResult, engine: str) -> StepResult:
        out.parent.mkdir(parents=True, exist_ok=True)
        note = ""
        if engine == _ENGINE_SYSTEM_TAR:
            fallback = _write_archive_system_tar(out, arcbase, walk.files)
            if fallback is not None:
                _write_archive(out, arcbase, walk.files)
                note = f" (system-tar unavailable: {fallback}; used python engine)"
        else:
            _write_archive(out, arcbase, walk.files)
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


def _normalize_items(source: Path, items: tuple[str, ...]) -> list[Path]:
    """Validate literal item paths and remove duplicate selected subtrees."""
    if not items:
        raise ValueError("items must not be empty")
    selected: list[Path] = []
    for item in items:
        relative = Path(os.path.normpath(item))
        if not item or relative.is_absolute() or relative == Path(".") or relative.parts[0].startswith(".."):
            raise ValueError(f"invalid item '{item}': must be a relative path inside the source")
        for parent in reversed(relative.parents):
            if parent != Path(".") and (source / parent).is_symlink():
                raise ValueError(f"item '{item}' passes through symlink '{parent.as_posix()}'")
        if relative not in selected and not any(parent in selected for parent in relative.parents):
            selected = [path for path in selected if relative not in path.parents]
            selected.append(relative)
    return selected


def _select_items(source: Path, base_state: ExcludeState, selected: list[Path]) -> tuple[WalkResult, list[str]]:
    """Select bundle members using source-relative excludes and ancestor rules."""
    files: list[Path] = []
    missing: list[str] = []
    total_bytes = file_count = 0
    states: dict[str, ExcludeState] = {str(source): state_for_directory(source, base_state)}
    applied: list[str] = []
    for relative in selected:
        path = source / relative
        if not os.path.lexists(path):
            missing.append(relative.as_posix())
            continue
        metadata = path.lstat()
        state = states[str(source)]
        for index, component in enumerate(relative.parts):
            ancestor = source.joinpath(*relative.parts[: index + 1])
            relpath = ancestor.relative_to(source).as_posix()
            if state.is_excluded(component, relpath):
                break
            if index < len(relative.parts) - 1:
                state = state_for_directory(ancestor, state)
                states[str(ancestor)] = state
                continue
            if stat.S_ISDIR(metadata.st_mode):
                subtree = _walk_tree(path, state, root=source)
                files.extend(subtree.files)
                file_count += subtree.file_count
                total_bytes += subtree.total_bytes
                applied.extend(subtree.applied)
            elif component != BKPIGNORE_FILENAME:
                if stat.S_ISREG(metadata.st_mode):
                    file_count += 1
                    total_bytes += metadata.st_size
                    files.append(path)
                elif stat.S_ISLNK(metadata.st_mode):
                    files.append(path)
    rules = list(dict.fromkeys([*_collect_applied(states), *applied]))
    return WalkResult(files, total_bytes, rules, file_count), missing


def _walk_tree(source: Path, base_state: ExcludeState, *, root: Path | None = None) -> WalkResult:
    """Walk ``source`` top-down, applying global excludes + path-scoped ``.bkpignore``.

    The exclude state at each directory is the ancestors' state layered with
    that directory's own ``.bkpignore`` (if any). Excluded directories are
    pruned from further descent; surviving regular files are collected.
    """
    files: list[Path] = []
    symlinks: list[Path] = []
    dirs: list[Path] = []
    total_bytes = 0
    if root is None:
        root = source
    states: dict[str, ExcludeState] = {str(source): state_for_directory(source, base_state)}

    for dirpath, dirnames, filenames in os.walk(source, onerror=_raise_walk_error):
        state = states[dirpath]

        # Record this surviving directory (the source root, then every descended
        # kept subdir) so it is archived non-recursively — otherwise an empty
        # directory, and an empty source tree's own `src/` entry, would vanish on
        # restore, unlike the former `tar -C ... source`.
        dirs.append(Path(dirpath))

        kept_dirs: list[str] = []
        for dirname in dirnames:
            child = os.path.join(dirpath, dirname)
            relpath = os.path.relpath(child, root).replace(os.sep, "/")
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
            relpath = os.path.relpath(file_path, root).replace(os.sep, "/")
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
        files=[*dirs, *files, *symlinks],
        total_bytes=total_bytes,
        applied=_collect_applied(states),
        file_count=len(files),
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


def _write_archive(out: Path, arcbase: Path, files: Iterable[Path]) -> None:
    """Stream a ``w:gz`` tarball of ``files`` to ``out`` atomically, ``chmod 600``.

    Replicates ``pybase.filesystem.atomic_write``'s tempfile + fsync +
    ``os.replace`` guarantee, but streams tar output straight into the temp file
    (a large tarball must never be built in memory, which the byte-oriented
    ``atomic_write_bytes`` would require). Archive names are stored relative to
    ``arcbase``: the source's parent for whole trees, or the source itself for
    selected items.
    """
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


def _write_archive_system_tar(out: Path, arcbase: Path, files: Iterable[Path]) -> str | None:
    """Archive ``files`` via system ``tar --null -T -``, atomically, ``chmod 600``.

    Python still owns selection: ``files`` is the exact include list the walk
    produced (surviving directories, files, and symlinks — so ``.bkpignore``
    path-scoping and empty-directory preservation hold). The paths, relative
    to ``arcbase``, are joined with NUL bytes and streamed to
    ``tar -C <arcbase> --no-recursion --null -T - -czf <tmp>`` on stdin.
    ``--no-recursion`` keeps the filtered list authoritative — a listed directory
    is archived as a bare entry, not re-expanded (which would re-add contents the
    walk excluded). NUL delimiting
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
            [tar_bin, "-C", str(arcbase), "--no-recursion", "--null", "-czf", str(tmp_path), "-T", "-"],
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


def _expand_stamp(pattern: str, now: datetime | None = None) -> str:
    """Expand ``strftime`` codes in an ``out`` pattern against the supplied or current time.

    A pattern like ``git-src-%Y%m%d-%H%M%S.tar.gz`` becomes a timestamped name
    at archive time, reproducing the wrapped script's ``date +%Y%m%d-%H%M%S``
    behaviour. A pattern with no ``%`` codes is returned unchanged.
    """
    if "%" not in pattern:
        return pattern
    return (now if now is not None else datetime.now()).strftime(pattern)


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()
