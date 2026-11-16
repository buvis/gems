"""``bim tx status``: the tiromex dashboard, computed on demand from the folder."""

from __future__ import annotations

import datetime as dt
import subprocess
from collections import Counter
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from bim.commands.tx.shared.format import (
    Assent,
    ConceptType,
    DoubtMode,
    Lifecycle,
    NoteKind,
    Relation,
    TxNote,
    as_datetime,
    link_file,
    read_note,
    relations,
    sources,
)
from bim.commands.tx.shared.paths import iter_note_files, read_last_maintain, to_vault_rel

if TYPE_CHECKING:
    from pathlib import Path

    from bim.commands.tx.shared.paths import TiromexPaths


def staleness(now: dt.datetime, window_days: int) -> tuple[str, int | None]:
    """Return ``(reason, days)`` for the last maintenance run.

    The reason is ``never``, ``unparseable``, ``stale`` (more than ``window_days``
    whole days ago) or ``fresh``; ``days`` is ``None`` for the first two.
    """
    raw = read_last_maintain()
    if not raw:
        return "never", None
    last = as_datetime(raw)
    if last is None:
        return "unparseable", None
    days = (now - last).days
    return ("stale" if days > window_days else "fresh"), days


def staleness_line(now: dt.datetime, window_days: int) -> tuple[bool, str]:
    """Return ``(stale, text)``: the maintenance line of the dashboard."""
    reason, days = staleness(now, window_days)
    if reason == "never":
        return True, "maintenance: never run (stale)"
    if reason == "unparseable":
        return True, "maintenance: last_maintain unparseable (stale)"
    if reason == "stale":
        return True, f"maintenance: last run {days}d ago (stale, window {window_days}d)"
    return False, f"maintenance: last run {days}d ago (fresh)"


def _corroboration(note: TxNote, notes: list[TxNote]) -> set[str]:
    """Return the sources of every note that supports ``note``, minus ``note``'s own sources."""
    supporters: set[str] = set()
    for other in notes:
        if any(
            rel == Relation.SUPPORTS.value and link_file(link.target) == note.path
            for rel, link in relations(other.data)
        ):
            supporters.update(sources(other.data))
    return supporters - set(sources(note.data))


def _is_prune_candidate(note: TxNote, notes: list[TxNote], now: dt.datetime, window_days: int) -> bool:
    meta = note.data.metadata
    if meta.get("lifecycle") != Lifecycle.FLEETING.value or meta.get("assent") == Assent.REJECTED.value:
        return False
    if meta.get("delivered-as") or relations(note.data):
        return False
    inbound = any(
        link_file(link.target) == note.path for other in notes if other is not note for _, link in relations(other.data)
    )
    if inbound or _corroboration(note, notes):
        return False
    anchor = as_datetime(meta.get("updated")) or as_datetime(meta.get("date"))
    return anchor is not None and now - anchor > dt.timedelta(days=window_days)


def _git_tracked(vault_root: Path) -> bool:
    argv = ["git", "-C", str(vault_root), "rev-parse", "--is-inside-work-tree"]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip() == "true"


def _fmt(counter: Counter[str]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items())) if counter else "(none)"


class CommandTxStatus:
    """Compute the tiromex dashboard: counts, links, doubts, prune candidates, git and staleness."""

    def __init__(
        self,
        paths: TiromexPaths,
        *,
        maintenance_window_days: int = 7,
        prune_window_days: int = 365,
        pruning_enabled: bool = False,
        now: dt.datetime | None = None,
    ) -> None:
        self.paths = paths
        self.maintenance_window_days = maintenance_window_days
        self.prune_window_days = prune_window_days
        self.pruning_enabled = pruning_enabled
        self.now = now

    def _read_notes(self) -> tuple[list[TxNote], list[str]]:
        notes: list[TxNote] = []
        warnings: list[str] = []
        for file in iter_note_files(self.paths):
            try:
                notes.append(read_note(self.paths, file))
            except (OSError, ValueError) as exc:
                warnings.append(f"skipped unparseable note {to_vault_rel(self.paths, file)}: {exc}")
        return notes, warnings

    def execute(self) -> CommandResult:
        """Read the folder and render the nine dashboard lines."""
        now = self.now or dt.datetime.now().astimezone()
        notes, warnings = self._read_notes()
        concepts = [note for note in notes if note.kind is NoteKind.CONCEPT]
        kinds = Counter(note.kind for note in notes)
        lifecycle = Counter(str(n.data.metadata["lifecycle"]) for n in concepts if n.data.metadata.get("lifecycle"))
        assent = Counter(str(n.data.metadata["assent"]) for n in concepts if n.data.metadata.get("assent"))
        links = sum(len(relations(note.data)) for note in concepts)
        mean_links = round(links / len(concepts), 2) if concepts else 0.0
        aporia = sum(1 for n in concepts if n.data.metadata.get("concept-type") == ConceptType.APORIA.value)
        disagreements = sum(
            1
            for n in concepts
            if isinstance(doubts := n.data.metadata.get("doubts"), list)
            for doubt in doubts
            if isinstance(doubt, dict) and doubt.get("mode") == DoubtMode.DISAGREEMENT.value
        )
        prune = sum(1 for n in concepts if _is_prune_candidate(n, notes, now, self.prune_window_days))
        lines = [
            f"tiromex: {self.paths.folder}",
            f"notes: {len(notes)} (concept: {kinds[NoteKind.CONCEPT]}, index: {kinds[NoteKind.INDEX]}, "
            f"runs: {kinds[NoteKind.RUN]}, plain: {kinds[NoteKind.PLAIN]})",
            f"lifecycle: {_fmt(lifecycle)}",
            f"assent: {_fmt(assent)}",
            f"mean links/note: {mean_links}",
            f"aporia notes: {aporia}  open disagreement doubts: {disagreements}",
            f"prune candidates: {prune} (deletion {'enabled' if self.pruning_enabled else 'report-only'})",
            "git: tracked" if _git_tracked(self.paths.vault_root) else "git: NOT a git work tree",
            staleness_line(now, self.maintenance_window_days)[1],
        ]
        metadata = {
            "zettels": len(concepts),
            "notes": len(notes),
            "lifecycle": dict(lifecycle),
            "assent": dict(assent),
            "mean_links": mean_links,
            "aporia": aporia,
            "open_disagreements": disagreements,
            "prune_candidates": prune,
            "pruning_enabled": self.pruning_enabled,
        }
        return CommandResult(success=True, output="\n".join(lines), warnings=warnings, metadata=metadata)
