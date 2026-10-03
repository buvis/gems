"""Install, refresh, and uninstall of operator asset packs.

Pure filesystem logic: no ``console``, no process exit. The command classes in
:mod:`klyreon.commands.assets` render these reports.

The hash-compare rules (install):

- File absent -> write it and record it.
- File present, hash matches the manifest AND the shipped content is identical
  -> leave it, report "current".
- File present, hash differs from the manifest -> the user edited it: back it up
  to ``<file>.klyreon-backup-YYYYMMDDHHmmSS``, then write the shipped version,
  report the displaced path.
- File present but absent from the manifest -> treat it as the user's: back it up
  the same way before writing.

Uninstall never reverts a human edit: a file whose hash still matches the
manifest is removed; a file whose hash differs is kept and reported. Manifest
entries are dropped either way, and only directories klyreon emptied are removed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from buvis.pybase.filesystem import atomic_write_bytes

from klyreon import __version__
from klyreon.assets.manifest import (
    ManifestEntry,
    load_manifest,
    save_manifest,
)
from klyreon.assets.registry import known_operator_names, payload_files, resolve_target

__all__ = [
    "AssetStatus",
    "InstallReport",
    "UninstallReport",
    "install",
    "refresh",
    "status",
    "uninstall",
]

_BACKUP_PREFIX = ".klyreon-backup-"


@dataclass(slots=True)
class InstallReport:
    """What one install/refresh pass did."""

    written: list[str] = field(default_factory=list)
    current: list[str] = field(default_factory=list)
    displaced: list[tuple[str, str]] = field(default_factory=list)  # (original, backup)

    def extend(self, other: InstallReport) -> None:
        self.written.extend(other.written)
        self.current.extend(other.current)
        self.displaced.extend(other.displaced)


@dataclass(slots=True)
class UninstallReport:
    """What one uninstall pass did."""

    removed: list[str] = field(default_factory=list)
    kept: list[tuple[str, str]] = field(default_factory=list)  # (path, reason)


@dataclass(frozen=True, slots=True)
class AssetStatus:
    """Per-file status for ``assets status``."""

    operator: str
    path: str
    recorded_version: str
    present: bool
    hash_matches: bool
    behind_cli: bool


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _backup_path(target: Path, moment: dt.datetime) -> Path:
    stamp = moment.strftime("%Y%m%d%H%M%S")
    return target.with_name(target.name + _BACKUP_PREFIX + stamp)


def _is_behind(recorded: str, running: str) -> bool:
    """Return True when ``recorded`` is an older version than ``running``."""
    from packaging.version import InvalidVersion, Version

    try:
        return Version(recorded) < Version(running)
    except InvalidVersion:
        # An unparseable recorded version is treated as not-behind: we cannot
        # order it, and guessing "behind" would nag on every status call.
        return False


def install(operators: list[str], *, now: dt.datetime | None = None) -> InstallReport:
    """Install (or refresh) each operator's pack, recording every file.

    Raises :class:`klyreon.assets.registry.UnknownOperatorError` for an unknown
    operator BEFORE touching any file, so a bad name writes nothing.
    """
    # Resolve everything up front so an unknown operator aborts before any write.
    resolved = {op: (resolve_target(op), payload_files(op)) for op in operators}

    manifest = load_manifest()
    moment = now or _now()
    report = InstallReport()

    for operator, (root, files) in resolved.items():
        for payload, handle in files:
            target = root / Path(payload.install_relpath)
            shipped = handle.read_bytes()
            shipped_hash = _sha256(shipped)
            abs_path = str(target)
            entry = manifest.entry_for_path(abs_path)

            if not target.exists():
                _write(target, shipped)
                manifest.upsert(_entry(operator, abs_path, shipped_hash, moment))
                report.written.append(abs_path)
                continue

            on_disk_hash = _sha256(target.read_bytes())
            if entry is not None and on_disk_hash == entry.sha256 and on_disk_hash == shipped_hash:
                report.current.append(abs_path)
                continue
            if entry is not None and on_disk_hash == entry.sha256:
                # Unmodified by the user but behind the shipped content: refresh,
                # no backup (nothing of the user's would be lost).
                _write(target, shipped)
                manifest.upsert(_entry(operator, abs_path, shipped_hash, moment))
                report.written.append(abs_path)
                continue

            # Either edited since we recorded it, or present-but-untracked: it is
            # the user's work. Back it up before overwriting.
            backup = _backup_path(target, moment)
            atomic_write_bytes(backup, target.read_bytes())
            _write(target, shipped)
            manifest.upsert(_entry(operator, abs_path, shipped_hash, moment))
            report.written.append(abs_path)
            report.displaced.append((abs_path, str(backup)))

    save_manifest(manifest)
    return report


def refresh(*, now: dt.datetime | None = None) -> InstallReport:
    """Re-install exactly the operators recorded in the manifest."""
    manifest = load_manifest()
    operators = sorted({e.operator for e in manifest.entries if e.kind == "asset"})
    if not operators:
        return InstallReport()
    return install(operators, now=now)


def status() -> list[AssetStatus]:
    """Return the per-file status of every recorded asset."""
    manifest = load_manifest()
    running = __version__
    out: list[AssetStatus] = []
    for entry in manifest.entries:
        if entry.kind != "asset":
            continue
        target = Path(entry.path)
        present = target.is_file()
        hash_matches = present and _sha256(target.read_bytes()) == entry.sha256
        out.append(
            AssetStatus(
                operator=entry.operator,
                path=entry.path,
                recorded_version=entry.klyreon_version,
                present=present,
                hash_matches=hash_matches,
                behind_cli=_is_behind(entry.klyreon_version, running),
            ),
        )
    return out


def uninstall(operators: list[str]) -> UninstallReport:
    """Remove klyreon's files for ``operators``; keep user-edited ones.

    Validates operator names against the registry first (unknown name aborts
    before any change). Drops manifest entries either way, and removes only
    directories klyreon emptied.
    """
    known = set(known_operator_names())
    unknown = [op for op in operators if op not in known]
    if unknown:
        from klyreon.assets.registry import UnknownOperatorError

        msg = f"unknown operator {unknown[0]!r}; known operators: {', '.join(sorted(known))}"
        raise UnknownOperatorError(msg)

    manifest = load_manifest()
    report = UninstallReport()
    wanted = set(operators)
    touched_dirs: set[Path] = set()

    for entry in list(manifest.entries):
        if entry.kind != "asset" or entry.operator not in wanted:
            continue
        target = Path(entry.path)
        if not target.exists():
            report.removed.append(entry.path)
            manifest.remove_path(entry.path)
            touched_dirs.add(target.parent)
            continue
        if _sha256(target.read_bytes()) == entry.sha256:
            target.unlink()
            report.removed.append(entry.path)
            touched_dirs.add(target.parent)
        else:
            report.kept.append((entry.path, "edited since install (hash differs); left in place"))
        manifest.remove_path(entry.path)

    save_manifest(manifest)
    _prune_empty_dirs(touched_dirs, operators)
    return report


def _entry(operator: str, abs_path: str, sha256: str, moment: dt.datetime) -> ManifestEntry:
    return ManifestEntry(
        kind="asset",
        operator=operator,
        path=abs_path,
        sha256=sha256,
        klyreon_version=__version__,
        installed_at=moment.isoformat(),
    )


def _write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(target, data)


def _prune_empty_dirs(dirs: set[Path], operators: list[str]) -> None:
    """Remove now-empty directories klyreon created, walking up to each root.

    From each touched directory, walk upward removing empty directories, stopping
    once a directory still holds something or the install root itself is reached
    and removed. Never ascends above an operator's install root.
    """
    roots = {resolve_target(op) for op in operators}
    for start in dirs:
        current = start
        # Only prune within a known root (never ascend past it).
        while _at_or_under_a_root(current, roots):
            if _remove_if_empty(current):
                current = current.parent
                continue
            break


def _at_or_under_a_root(path: Path, roots: set[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _remove_if_empty(directory: Path) -> bool:
    """Remove ``directory`` and return True if it was empty; else return False."""
    if not directory.is_dir():
        return False
    try:
        next(directory.iterdir())
    except StopIteration:
        try:
            directory.rmdir()
        except OSError:
            return False
        return True
    except OSError:
        return False
    return False
