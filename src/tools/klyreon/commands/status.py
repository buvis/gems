"""``klyreon status`` -- print the vault dashboard, computed on demand."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from pathlib import Path

from buvis.pybase.result import CommandResult

from klyreon.spec.enums import ConceptType, DoubtMode
from klyreon.spec.model import FileKind
from klyreon.spec.parser import FrontmatterError, parse_file
from klyreon.vault.git import is_git_vault
from klyreon.vault.state import read_state


class CommandStatus:
    """Compute and render the vault dashboard entirely from the vault on demand.

    No index file. Counts by lifecycle and assent, totals, mean links per
    zettel, aporia count, open disagreement-doubt count, pending inbox sources,
    git status, and the maintenance-staleness line.
    """

    def __init__(
        self,
        root: Path,
        *,
        maintenance_window_days: int = 7,
        now: dt.datetime | None = None,
        check_assets: bool = False,
    ) -> None:
        self.root = root
        self.maintenance_window_days = maintenance_window_days
        self.now = now
        self.check_assets = check_assets

    def execute(self) -> CommandResult:
        notes_dir = self.root / "wiki" / "notes"
        sources_dir = self.root / "sources"

        lifecycle_counts: Counter[str] = Counter()
        assent_counts: Counter[str] = Counter()
        total_zettels = 0
        total_links = 0
        aporia = 0
        open_disagreements = 0
        warnings: list[str] = []

        if notes_dir.is_dir():
            for md in sorted(notes_dir.rglob("*.md")):
                try:
                    doc = parse_file(md, FileKind.ZETTEL)
                except (FrontmatterError, OSError) as exc:
                    warnings.append(f"skipped unparseable zettel {md.name}: {exc}")
                    continue
                total_zettels += 1
                if doc.get("lifecycle"):
                    lifecycle_counts[str(doc.get("lifecycle"))] += 1
                if doc.get("assent"):
                    assent_counts[str(doc.get("assent"))] += 1
                total_links += len(doc.get("links") or [])
                if doc.get("concept-type") == ConceptType.APORIA.value:
                    aporia += 1
                for doubt in doc.get("doubts") or []:
                    if isinstance(doubt, dict) and doubt.get("mode") == DoubtMode.DISAGREEMENT.value:
                        open_disagreements += 1

        total_sources, pending_sources = self._count_sources(sources_dir)
        mean_links = round(total_links / total_zettels, 2) if total_zettels else 0.0
        git_line = "git: tracked" if is_git_vault(self.root) else "git: NOT a git work tree"
        staleness = self._staleness_line()

        self._warn_assets_behind(warnings)

        lines = [
            f"vault: {self.root}",
            f"zettels: {total_zettels}  sources: {total_sources} (pending inbox: {pending_sources})",
            f"lifecycle: {self._fmt(lifecycle_counts)}",
            f"assent: {self._fmt(assent_counts)}",
            f"mean links/zettel: {mean_links}",
            f"aporia zettels: {aporia}  open disagreement doubts: {open_disagreements}",
            git_line,
            staleness,
        ]
        return CommandResult(
            success=True,
            output="\n".join(lines),
            warnings=warnings,
            metadata={
                "zettels": total_zettels,
                "sources": total_sources,
                "pending_sources": pending_sources,
                "lifecycle": dict(lifecycle_counts),
                "assent": dict(assent_counts),
                "mean_links": mean_links,
                "aporia": aporia,
                "open_disagreements": open_disagreements,
            },
        )

    @staticmethod
    def _fmt(counter: Counter[str]) -> str:
        if not counter:
            return "(none)"
        return ", ".join(f"{k}={v}" for k, v in sorted(counter.items()))

    def _count_sources(self, sources_dir: Path) -> tuple[int, int]:
        if not sources_dir.is_dir():
            return 0, 0
        total = 0
        pending = 0
        for md in sources_dir.rglob("*.md"):
            total += 1
            # "archive/" subtree is committed; everything else is the inbox.
            if "archive" not in md.relative_to(sources_dir).parts:
                pending += 1
        return total, pending

    def _warn_assets_behind(self, warnings: list[str]) -> None:
        """Append exactly one warning when any installed asset is behind the CLI.

        Off unless ``check_assets`` is set: the asset check belongs to the health
        dashboard, not to every command invocation. A broken manifest never
        breaks the dashboard -- the warning is simply skipped.
        """
        if not self.check_assets:
            return
        try:
            from klyreon.assets import installer
            from klyreon.assets.manifest import ManifestError

            try:
                behind = [s for s in installer.status() if s.behind_cli]
            except ManifestError:
                return
        except ImportError:
            return
        if behind:
            operators = ", ".join(sorted({s.operator for s in behind}))
            warnings.append(
                f"installed assets are behind this klyreon ({operators}): run 'klyreon assets refresh' to update them",
            )

    def _staleness_line(self) -> str:
        now = self.now or dt.datetime.now().astimezone()
        last = read_state().get("last_maintain")
        if not last:
            return "maintenance: never run (stale)"
        parsed = self._parse(last)
        if parsed is None:
            return "maintenance: last_maintain unparseable (stale)"
        age = now - parsed
        if age > dt.timedelta(days=self.maintenance_window_days):
            return f"maintenance: last run {age.days}d ago (stale, window {self.maintenance_window_days}d)"
        return f"maintenance: last run {age.days}d ago (fresh)"

    @staticmethod
    def _parse(value: object) -> dt.datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return dt.datetime.fromisoformat(value)
        except ValueError:
            return None
