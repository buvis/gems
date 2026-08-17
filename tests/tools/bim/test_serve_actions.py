from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from buvis.pybase.result import CommandResult
from starlette.testclient import TestClient

# (action, command_path, output) — one entry per action, used by the
# success-envelope matrix below.
ACTION_SUCCESS_CASES = [
    ("sync_note", "bim.commands.sync_note.sync_note.CommandSyncNote", "synced"),
    ("create_note", "bim.commands.create_note.create_note.CommandCreateNote", "created"),
    ("archive", "bim.commands.archive_note.archive_note.CommandArchiveNote", "archived"),
    ("delete", "bim.commands.delete_note.delete_note.CommandDeleteNote", "deleted"),
    ("format", "bim.commands.format_note.format_note.CommandFormatNote", "formatted"),
    ("import", "bim.commands.import_note.import_note.CommandImportNote", "imported"),
]

# (action, command_path, error) — one entry per action, used by the
# failure-envelope matrix below.
ACTION_FAILURE_CASES = [
    ("sync_note", "bim.commands.sync_note.sync_note.CommandSyncNote", "sync failed"),
    ("create_note", "bim.commands.create_note.create_note.CommandCreateNote", "create failed"),
    ("archive", "bim.commands.archive_note.archive_note.CommandArchiveNote", "archive failed"),
    ("delete", "bim.commands.delete_note.delete_note.CommandDeleteNote", "delete failed"),
    ("format", "bim.commands.format_note.format_note.CommandFormatNote", "format failed"),
    ("import", "bim.commands.import_note.import_note.CommandImportNote", "import failed"),
]

# (action, mock_target) — one entry per action, used by the
# outside-vault-403 matrix below.
ACTION_OUTSIDE_VAULT_CASES = [
    ("sync_note", "bim.commands.sync_note.sync_note.CommandSyncNote"),
    ("create_note", "bim.commands.create_note.create_note.CommandCreateNote"),
    ("archive", "bim.commands.archive_note.archive_note.CommandArchiveNote"),
    ("open", "bim.commands.serve._actions.open_in_os"),
    ("format", "bim.commands.format_note.format_note.CommandFormatNote"),
    ("delete", "bim.commands.delete_note.delete_note.CommandDeleteNote"),
    ("import", "bim.commands.import_note.import_note.CommandImportNote"),
]


class TestServeActions:
    def test_exec_action_without_token_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/actions/some-action",
            json={"file_path": "note.md", "args": {}, "row": {}},
        )

        assert response.status_code == 401

    def test_exec_action_with_non_ascii_token_header_returns_401(self, client: TestClient) -> None:
        """A non-ASCII ``X-Buvis-Token`` header (raw byte 0xE9, which
        Starlette decodes as latin-1) must not crash the comparison into an
        uncaught 500; it must fail closed with the documented 401."""
        response = client.post(
            "/api/actions/some-action",
            json={"file_path": "note.md", "args": {}, "row": {}},
            headers=[(b"X-Buvis-Token", b"\xe9")],
        )

        assert response.status_code == 401

    def test_patch_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.serve._actions.get_repo") as mock_get_repo:
            response = client.post(
                "/api/actions/patch",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_get_repo.assert_not_called()

    def test_patch_action_success_returns_200(self, client: TestClient, tmp_path: Path) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(
                success=True,
                output="Updated note.md",
                metadata={"updated_count": 1},
            )

            response = client.post(
                "/api/actions/patch",
                json={
                    "file_path": str(real_file),
                    "args": {"field": "title", "value": "New Title"},
                    "row": {},
                },
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_patch_action_failure_returns_422(self, client: TestClient, tmp_path: Path) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(
                success=False,
                error="No changes provided",
            )

            response = client.post(
                "/api/actions/patch",
                json={
                    "file_path": str(real_file),
                    "args": {"field": "title", "value": "New Title"},
                    "row": {},
                },
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "No changes provided"

    @pytest.mark.parametrize(
        "action,mock_target", ACTION_OUTSIDE_VAULT_CASES, ids=[c[0] for c in ACTION_OUTSIDE_VAULT_CASES]
    )
    def test_action_outside_vault_returns_403(self, client: TestClient, action: str, mock_target: str) -> None:
        client.app.state.buvis_token = "test-token"

        with patch(mock_target) as mock_command:
            response = client.post(
                f"/api/actions/{action}",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_command.assert_not_called()

    def test_open_action_in_vault_with_valid_token_returns_200_and_opens_resolved_path(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._actions.open_in_os") as mock_open_in_os:
            response = client.post(
                "/api/actions/open",
                json={"file_path": str(real_file), "args": {}, "row": {}},
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )

        assert response.status_code == 200
        mock_open_in_os.assert_called_once_with(real_file.resolve())

    def test_open_action_success_returns_full_envelope(self, client: TestClient, tmp_path: Path) -> None:
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._actions.open_in_os"):
            response = client.post(
                "/api/actions/open",
                json={"file_path": str(real_file), "args": {}, "row": {}},
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "output": None,
            "error": None,
            "info": [],
            "warnings": [],
            "metadata": {},
        }

    @pytest.mark.parametrize(
        "action,command_path,output", ACTION_SUCCESS_CASES, ids=[c[0] for c in ACTION_SUCCESS_CASES]
    )
    def test_action_success_returns_200(
        self, client: TestClient, tmp_path: Path, action: str, command_path: str, output: str
    ) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch(command_path) as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(success=True, output=output)

            response = client.post(
                f"/api/actions/{action}",
                json={"file_path": str(real_file), "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.parametrize(
        "action,command_path,error", ACTION_FAILURE_CASES, ids=[c[0] for c in ACTION_FAILURE_CASES]
    )
    def test_action_failure_returns_422(
        self, client: TestClient, tmp_path: Path, action: str, command_path: str, error: str
    ) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch(command_path) as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(success=False, error=error)

            response = client.post(
                f"/api/actions/{action}",
                json={"file_path": str(real_file), "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"] == error


class TestServeErrors:
    def test_unknown_action_returns_404(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"
        response = client.post(
            "/api/actions/missing",
            json={"file_path": "note.md", "args": {}, "row": {}},
            headers={"X-Buvis-Token": "test-token"},
        )

        assert response.status_code == 404
        assert "Unknown action" in response.json()["detail"]
