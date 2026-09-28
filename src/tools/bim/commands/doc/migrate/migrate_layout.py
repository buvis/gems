"""CommandMigrateLayout — migrate legacy flat-layout zettels to v1 per-issuer.

``bim doc audit`` reports ``legacy_layout_zettels``: document zettels still
at the pre-v1 flat path (``<vault>/<doc-subdir>/<basename>.md``) instead of
the per-issuer path (``<vault>/<doc-subdir>/<issuer-slug>/<basename>.md``).
This command consumes that list and moves each such zettel into its
per-issuer subfolder. The file's content — including the ``file-path``
frontmatter link — is **preserved byte-for-byte**: that link already points
at the PDF's per-issuer location, so nothing in the zettel needs rewriting;
only the ``.md`` file itself moves.

Design invariants:

- **Dry-run by default.** ``dry_run`` (default True) computes the plan and
  touches nothing. ``--apply`` performs the moves.
- **Crash-atomic, no-clobber move.** Each move is ``os.link(source, target)``
  followed by ``source.unlink()``. ``os.link`` is a single atomic syscall
  that refuses to overwrite an existing target (no-clobber), and a crash
  between the two steps leaves two hardlinks to the same inode — identical
  content, no data loss — never a partial file.
- **Skip and report, never partial.** A legacy zettel whose frontmatter is
  unparseable, whose per-issuer target cannot be derived, or whose target
  already exists is skipped and reported; the run continues with the rest.
  Every filesystem error becomes a reported skip — ``_apply`` never raises.

The command returns a :class:`CommandResult`; the CLI layer renders it.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.naming import SLUG_REGEX

__all__ = ["CommandMigrateLayout", "MigratePlanItem", "MigrateServices", "MigrateSkip"]

_FRONTMATTER_RE = re.compile(r"^---\n(?P<yaml>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)
_FILE_LINK_RE = re.compile(r"\[[^\]]*\]\(file://(?P<url>[^)]*)\)")


@dataclass(frozen=True)
class MigrateServices:
    """Boundary inputs CommandMigrateLayout depends on.

    ``legacy_zettels`` is the list of legacy flat-layout zettel paths (the
    ``legacy_layout_zettels`` contract from the latest audit). ``vault_root``
    and ``vault_documents_subdir`` locate the per-issuer target base dir.
    """

    legacy_zettels: tuple[str, ...]
    vault_root: Path
    vault_documents_subdir: str


@dataclass(frozen=True)
class MigratePlanItem:
    """A single planned move: ``source`` (legacy flat path) -> ``target``."""

    source: Path
    target: Path
    issuer_slug: str


@dataclass(frozen=True)
class MigrateSkip:
    """A legacy zettel that could not be migrated safely."""

    source: Path
    reason: str


@dataclass
class _Resolution:
    """Outcome of resolving one legacy zettel: either a plan item or a skip."""

    plan: MigratePlanItem | None = None
    skip: MigrateSkip | None = None


@dataclass
class CommandMigrateLayout:
    """Migrate legacy flat-layout zettels to the v1 per-issuer layout."""

    services: MigrateServices
    dry_run: bool = True
    _planned: list[MigratePlanItem] = field(default_factory=list, init=False)
    _skipped: list[MigrateSkip] = field(default_factory=list, init=False)

    def execute(self) -> CommandResult:
        base_dir = self.services.vault_root / self.services.vault_documents_subdir
        migrated: list[MigratePlanItem] = []
        skipped: list[MigrateSkip] = []
        planned: list[MigratePlanItem] = []

        for raw in self.services.legacy_zettels:
            source = Path(raw)
            resolution = self._resolve(source, base_dir)
            if resolution.skip is not None:
                skipped.append(resolution.skip)
                continue
            plan = resolution.plan
            assert plan is not None  # noqa: S101 - resolve guarantees plan xor skip
            planned.append(plan)
            if self.dry_run:
                continue
            apply_skip = self._apply(plan)
            if apply_skip is not None:
                skipped.append(apply_skip)
            else:
                migrated.append(plan)

        return self._build_result(planned=planned, migrated=migrated, skipped=skipped)

    # --------- per-file resolution ---------

    def _resolve(self, source: Path, base_dir: Path) -> _Resolution:
        parsed = self._read_frontmatter(source)
        if isinstance(parsed, str):
            return _Resolution(skip=MigrateSkip(source, parsed))
        data = parsed

        file_path_value = data.get("file-path")
        if not isinstance(file_path_value, str) or not file_path_value:
            return _Resolution(skip=MigrateSkip(source, "frontmatter missing file-path"))

        issuer_slug = self._derive_issuer_slug(file_path_value)
        if issuer_slug is None:
            return _Resolution(skip=MigrateSkip(source, "could not derive issuer slug from file-path"))

        target = base_dir / issuer_slug / source.name
        skip_reason = self._target_skip_reason(source, target)
        if skip_reason is not None:
            return _Resolution(skip=MigrateSkip(source, skip_reason))

        return _Resolution(plan=MigratePlanItem(source=source, target=target, issuer_slug=issuer_slug))

    @staticmethod
    def _read_frontmatter(source: Path) -> dict[str, object] | str:
        """Return the parsed frontmatter mapping, or an error string to skip on."""
        if not source.is_file():
            return "legacy zettel not found on disk"
        try:
            raw_text = source.read_text(encoding="utf-8")
        except OSError as exc:
            return f"could not read: {exc}"
        match = _FRONTMATTER_RE.match(raw_text)
        if match is None:
            return "no YAML frontmatter block"
        try:
            data = yaml.safe_load(match.group("yaml"))
        except yaml.YAMLError as exc:
            return f"unparseable frontmatter: {exc}"
        if not isinstance(data, dict):
            return "frontmatter is not a mapping"
        return data

    @staticmethod
    def _target_skip_reason(source: Path, target: Path) -> str | None:
        """Return a skip reason if the per-issuer target is unusable, else ``None``."""
        if target == source:
            return "already at the per-issuer path"
        if target.exists():
            return f"per-issuer target already exists: {target}"
        return None

    @staticmethod
    def _derive_issuer_slug(file_path_value: str) -> str | None:
        """Extract the issuer slug (the PDF's parent-dir name) from ``file-path``.

        ``file-path`` is a Markdown link wrapping a URL-encoded ``file://``
        URL, e.g. ``"[Open file](file:///.../Business/cez-as/x.invoice.pdf)"``.
        The issuer slug is the name of the directory containing the PDF. It
        must be a valid kebab-case slug for the move to be safe.
        """
        link = _FILE_LINK_RE.search(file_path_value)
        raw_url = link.group("url") if link else file_path_value
        decoded = urllib.parse.unquote(raw_url)
        pdf_path = Path(decoded)
        parent_name = pdf_path.parent.name
        if not parent_name or not SLUG_REGEX.match(parent_name):
            return None
        return parent_name

    # --------- apply ---------

    def _apply(self, plan: MigratePlanItem) -> MigrateSkip | None:
        """Crash-atomically move the zettel into its per-issuer target.

        The zettel content is preserved byte-for-byte (the ``file-path`` link
        already points at the PDF's per-issuer location, so only the file
        moves), and source and target share the vault filesystem — so the move
        is a hardlink + unlink rather than a copy:

        - ``os.link(source, target)`` is a single atomic syscall that FAILS
          (``FileExistsError``) if the target already exists, giving a
          no-clobber guarantee even against a concurrent run that created the
          target after the earlier ``_target_skip_reason`` check.
        - A crash between the link and the unlink leaves two hardlinks to the
          *same inode* — identical content, no data loss — and a re-run's
          exists-guard then skips it. There is no window in which data is lost
          or a partial file exists.

        Returns a :class:`MigrateSkip` on filesystem error, else ``None``.
        This method never raises — every OS error becomes a reported skip.
        """
        try:
            plan.target.parent.mkdir(parents=True, exist_ok=True)
            os.link(plan.source, plan.target)
        except FileExistsError:
            return MigrateSkip(plan.source, f"per-issuer target already exists: {plan.target}")
        except OSError as exc:
            return MigrateSkip(plan.source, f"move failed: {exc}")
        try:
            plan.source.unlink()
        except OSError as exc:
            # The target hardlink is already in place (same inode as source),
            # so no data is lost; report that the legacy link could not be
            # removed and leave both in place for a re-run to reconcile.
            return MigrateSkip(plan.source, f"moved but could not remove legacy file: {exc}")
        return None

    # --------- result ---------

    def _build_result(
        self,
        *,
        planned: list[MigratePlanItem],
        migrated: list[MigratePlanItem],
        skipped: list[MigrateSkip],
    ) -> CommandResult:
        warnings = [f"skipped {skip.source}: {skip.reason}" for skip in skipped]
        if self.dry_run:
            output = f"dry-run: {len(planned)} zettel(s) would migrate, {len(skipped)} skipped"
            info = [f"would move {item.source} -> {item.target}" for item in planned]
            return CommandResult(
                success=True,
                output=output,
                info=info,
                warnings=warnings,
                metadata={
                    "dry_run": True,
                    "planned_count": len(planned),
                    "skipped_count": len(skipped),
                    "planned": [
                        {"source": str(i.source), "target": str(i.target), "issuer_slug": i.issuer_slug}
                        for i in planned
                    ],
                    "skipped": [{"source": str(s.source), "reason": s.reason} for s in skipped],
                },
            )

        output = f"migrated {len(migrated)} zettel(s), {len(skipped)} skipped"
        info = [f"moved {item.source} -> {item.target}" for item in migrated]
        return CommandResult(
            success=True,
            output=output,
            info=info,
            warnings=warnings,
            metadata={
                "dry_run": False,
                "migrated_count": len(migrated),
                "skipped_count": len(skipped),
                "migrated": [
                    {"source": str(i.source), "target": str(i.target), "issuer_slug": i.issuer_slug} for i in migrated
                ],
                "skipped": [{"source": str(s.source), "reason": s.reason} for s in skipped],
            },
        )
