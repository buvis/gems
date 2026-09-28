"""TestClient tests for the triage serve actions (PRD 00057).

Exercises the generic ``POST /api/actions/{name}`` route for ``triage_list``
and ``triage_approve``: 200 on success, 422 + envelope on failure, and the
403 confinement guard on a proposal path outside the allowed roots.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from buvis.pybase.result import CommandResult
from starlette.testclient import TestClient

_TOKEN = "test-token"


@pytest.fixture
def doc_client(tmp_path: Path):
    """A TestClient whose app has doc_settings + a business_triage_root set."""
    from bim.commands.serve._app import create_app

    vault = tmp_path / "zettels"
    vault.mkdir()
    triage = tmp_path / "Business" / "_triage"
    triage.mkdir(parents=True)
    doc_settings = MagicMock()  # handlers pass it to patched dependency factories
    with (
        patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
        patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
    ):
        app = create_app(
            default_directory=str(vault),
            archive_directory=None,
            business_triage_root=str(triage),
            doc_settings=doc_settings,
        )
        app.state.buvis_token = _TOKEN
        with TestClient(app, base_url="http://127.0.0.1") as client:
            client._triage_dir = triage  # type: ignore[attr-defined]
            yield client


class TestTriageListAction:
    def test_success_returns_200(self, doc_client: TestClient) -> None:
        with (
            patch("bim.commands.doc.triage.triage.CommandTriageList") as mk,
            patch("bim.dependencies.get_triage_list_services", return_value=MagicMock()),
        ):
            mk.return_value.execute.return_value = CommandResult(
                success=True, output="1 pending", metadata={"count": 1, "proposals": []}
            )
            resp = doc_client.post(
                "/api/actions/triage_list",
                json={"file_path": "", "args": {}, "row": {}},
                headers={"X-Buvis-Token": _TOKEN},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_failure_returns_422_with_envelope(self, doc_client: TestClient) -> None:
        with (
            patch("bim.commands.doc.triage.triage.CommandTriageList") as mk,
            patch("bim.dependencies.get_triage_list_services", return_value=MagicMock()),
        ):
            mk.return_value.execute.return_value = CommandResult(success=False, error="triage list failed")
            resp = doc_client.post(
                "/api/actions/triage_list",
                json={"file_path": "", "args": {}, "row": {}},
                headers={"X-Buvis-Token": _TOKEN},
            )
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "triage list failed"

    def test_without_token_returns_401(self, doc_client: TestClient) -> None:
        resp = doc_client.post("/api/actions/triage_list", json={"file_path": "", "args": {}, "row": {}})
        assert resp.status_code == 401


class TestTriageApproveAction:
    def _proposal(self, doc_client: TestClient) -> Path:
        triage = doc_client._triage_dir  # type: ignore[attr-defined]
        proposal = triage / "x.pdf.proposed.yml"
        proposal.write_text("approved: false\n", encoding="utf-8")
        return proposal

    def test_success_returns_200(self, doc_client: TestClient) -> None:
        proposal = self._proposal(doc_client)
        with (
            patch("bim.commands.doc.triage.triage.CommandTriageApprove") as mk,
            patch("bim.dependencies.get_triage_approve_services", return_value=MagicMock()),
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            mk.return_value.execute.return_value = CommandResult(
                success=True, metadata={"zettel_path": "/z.md", "pdf_path": "/p.pdf"}
            )
            resp = doc_client.post(
                "/api/actions/triage_approve",
                json={"file_path": str(proposal), "args": {}, "row": {}},
                headers={"X-Buvis-Token": _TOKEN},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_failure_returns_422_with_envelope(self, doc_client: TestClient) -> None:
        proposal = self._proposal(doc_client)
        with (
            patch("bim.commands.doc.triage.triage.CommandTriageApprove") as mk,
            patch("bim.dependencies.get_triage_approve_services", return_value=MagicMock()),
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            mk.return_value.execute.return_value = CommandResult(success=False, error="approved must be true")
            resp = doc_client.post(
                "/api/actions/triage_approve",
                json={"file_path": str(proposal), "args": {}, "row": {}},
                headers={"X-Buvis-Token": _TOKEN},
            )
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "approved must be true"

    def test_path_outside_roots_returns_403(self, doc_client: TestClient) -> None:
        with patch("bim.commands.doc.triage.triage.CommandTriageApprove") as mk:
            resp = doc_client.post(
                "/api/actions/triage_approve",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": _TOKEN},
            )
        assert resp.status_code == 403
        mk.assert_not_called()
