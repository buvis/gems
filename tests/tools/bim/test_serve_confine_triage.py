"""confine_path tests for the doc-triage allow-list addition (PRD 00057).

The ``_triage/`` directory lives under ``business_root``, which is NOT the
zettel vault (``default_directory``) nor the archive. The triage_approve
action must be able to resolve a proposal path under ``_triage/``, so
``AppState.business_triage_root`` is added to the confine_path allow-list.
A path outside every allowed root must still 403.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bim.commands.serve._security import AppState, confine_path
from fastapi import HTTPException


def _app_state(tmp_path: Path) -> AppState:
    vault = tmp_path / "Vault"
    triage = tmp_path / "Business" / "_triage"
    vault.mkdir(parents=True, exist_ok=True)
    triage.mkdir(parents=True, exist_ok=True)
    return AppState(
        default_directory=str(vault),
        archive_directory=None,
        business_triage_root=str(triage),
    )


class TestConfinePathTriageRoot:
    def test_triage_path_now_resolves(self, tmp_path: Path) -> None:
        state = _app_state(tmp_path)
        proposal = tmp_path / "Business" / "_triage" / "x.pdf.proposed.yml"
        proposal.write_text("approved: false\n", encoding="utf-8")

        resolved = confine_path(str(proposal), state)
        assert resolved == proposal.resolve()

    def test_vault_path_still_resolves(self, tmp_path: Path) -> None:
        state = _app_state(tmp_path)
        note = tmp_path / "Vault" / "note.md"
        note.write_text("x", encoding="utf-8")
        assert confine_path(str(note), state) == note.resolve()

    def test_path_outside_all_roots_still_403s(self, tmp_path: Path) -> None:
        state = _app_state(tmp_path)
        with pytest.raises(HTTPException) as exc:
            confine_path("/etc/passwd", state)
        assert exc.value.status_code == 403

    def test_no_triage_root_configured_rejects_triage_path(self, tmp_path: Path) -> None:
        """With business_triage_root unset, a _triage path is outside the roots."""
        vault = tmp_path / "Vault"
        vault.mkdir(parents=True, exist_ok=True)
        state = AppState(default_directory=str(vault), archive_directory=None)
        proposal = tmp_path / "Business" / "_triage" / "x.pdf.proposed.yml"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        proposal.write_text("approved: false\n", encoding="utf-8")
        with pytest.raises(HTTPException) as exc:
            confine_path(str(proposal), state)
        assert exc.value.status_code == 403
