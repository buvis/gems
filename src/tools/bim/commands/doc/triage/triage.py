"""Triage review surface — list pending proposals and approve+promote them.

Reviewing a triaged PDF previously meant locating the proposal YAML under
``<business_root>/_triage/``, hand-editing ``approved: true``, then running
``bim doc promote <path>``. These two commands replace that dance:

- :class:`CommandTriageList` enumerates ``<business_root>/_triage/*.proposed.yml``
  and returns the reviewer-facing fields for each (issuer, doc type, date,
  triage reasons, path).
- :class:`CommandTriageApprove` sets a proposal ``approved`` and promotes it
  via the existing collision-safe :class:`CommandPromote`.

Both return a :class:`CommandResult`; the CLI and the serve action registry
render it. No ``sys.exit`` / ``console.*`` in the command classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.triage import read_proposal, write_proposal

if TYPE_CHECKING:
    from bim.commands.doc.promote.promote import PromoteServices
    from bim.commands.doc.shared.settings_models import DocSettings
    from bim.params.doc_triage import TriageApproveParams, TriageListParams

__all__ = [
    "CommandTriageApprove",
    "CommandTriageList",
    "TriageApproveServices",
    "TriageListServices",
]

_PROPOSAL_SUFFIX = ".proposed.yml"


@dataclass(frozen=True)
class TriageListServices:
    """Boundary inputs for :class:`CommandTriageList`."""

    business_root: Path


@dataclass(frozen=True)
class TriageApproveServices:
    """Boundary inputs for :class:`CommandTriageApprove`.

    ``settings`` and ``promote_services`` are exactly what ``CommandPromote``
    needs; the approve command sets ``approved`` on disk, then delegates the
    filing to that command so there is one promote implementation.
    """

    settings: DocSettings
    promote_services: PromoteServices


@dataclass(frozen=True)
class _ProposalRow:
    """Reviewer-facing summary of one pending proposal."""

    path: str
    issuer_slug: str
    issuer_display: str
    doc_type: str
    doc_date: str | None
    title: str | None
    triage_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "issuer_slug": self.issuer_slug,
            "issuer_display": self.issuer_display,
            "doc_type": self.doc_type,
            "doc_date": self.doc_date,
            "title": self.title,
            "triage_reasons": list(self.triage_reasons),
        }


@dataclass
class CommandTriageList:
    """Enumerate pending triage proposals under ``<business_root>/_triage/``."""

    services: TriageListServices
    params: TriageListParams | None = None

    def execute(self) -> CommandResult:
        triage_dir = self.services.business_root / "_triage"
        if not triage_dir.is_dir():
            return CommandResult(
                success=True,
                output="no pending triage proposals (no _triage/ directory)",
                metadata={"proposals": [], "count": 0},
            )

        rows: list[_ProposalRow] = []
        warnings: list[str] = []
        for path in sorted(triage_dir.iterdir(), key=lambda p: p.name):
            if not (path.is_file() and path.name.endswith(_PROPOSAL_SUFFIX)):
                continue
            row = self._read_row(path)
            if isinstance(row, str):
                warnings.append(f"skipped {path}: {row}")
                continue
            rows.append(row)

        return CommandResult(
            success=True,
            output=f"{len(rows)} pending triage proposal(s)",
            info=[f"{r.path} — {r.issuer_slug}/{r.doc_type}" for r in rows],
            warnings=warnings,
            metadata={"proposals": [r.to_dict() for r in rows], "count": len(rows)},
        )

    @staticmethod
    def _read_row(path: Path) -> _ProposalRow | str:
        try:
            proposal = read_proposal(path)
        except Exception as exc:  # report any parse failure, keep listing the rest
            return f"could not read proposal: {exc}"
        return _ProposalRow(
            path=str(path),
            issuer_slug=proposal.issuer.slug,
            issuer_display=proposal.issuer.display_name,
            doc_type=proposal.document.type,
            doc_date=proposal.document.date.isoformat() if proposal.document.date else None,
            title=proposal.document.title,
            triage_reasons=tuple(proposal.triage_reasons),
        )


@dataclass
class CommandTriageApprove:
    """Set a triage proposal approved and promote it via ``CommandPromote``."""

    services: TriageApproveServices
    params: TriageApproveParams

    def execute(self) -> CommandResult:
        proposal_path = self.params.proposed_yml_path
        if not proposal_path.is_file():
            return CommandResult(success=False, error=f"proposal not found: {proposal_path}")
        if not proposal_path.name.endswith(_PROPOSAL_SUFFIX):
            return CommandResult(
                success=False,
                error=f"not a triage proposal (expected *{_PROPOSAL_SUFFIX}): {proposal_path}",
            )

        try:
            proposal = read_proposal(proposal_path)
        except Exception as exc:  # surface any parse failure as a CommandResult
            return CommandResult(success=False, error=f"could not read proposal: {exc}")

        if not proposal.approved:
            approved = proposal.model_copy(update={"approved": True})
            try:
                write_proposal(proposal_path, approved)
            except OSError as exc:
                return CommandResult(success=False, error=f"could not write approval: {exc}")

        return self._promote(proposal_path)

    def _promote(self, proposal_path: Path) -> CommandResult:
        from bim.commands.doc.promote.promote import CommandPromote
        from bim.params.doc_promote import PromoteParams

        cmd = CommandPromote(
            params=PromoteParams(proposed_yml_path=proposal_path),
            settings=self.services.settings,
            services=self.services.promote_services,
        )
        return cmd.execute()
