from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from buvis.pybase.result import CommandResult
from starlette.testclient import TestClient


class TestServeZettels:
    def test_get_zettel(self, client: TestClient, tmp_path: Path) -> None:
        file_path = tmp_path / "zettels" / "note.md"
        data = SimpleNamespace(
            metadata={"title": "Note"},
            reference={"ref": "A1"},
            sections=[("Heading", "Body")],
            file_path="note.md",
        )
        zettel = MagicMock()
        zettel.get_data.return_value = data
        repo = MagicMock()
        repo.find_by_location.return_value = zettel

        with (
            patch("pathlib.Path.is_file", return_value=True),
            patch("bim.commands.serve._routes.get_repo", return_value=repo),
        ):
            response = client.get(f"/api/zettels/{file_path}")

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["title"] == "Note"
        assert body["reference"]["ref"] == "A1"
        assert body["sections"] == [{"heading": "Heading", "body": "Body"}]
        assert body["file_path"] == "note.md"
        repo.find_by_location.assert_called_once_with(str(file_path))

    def test_get_zettel_outside_vault_returns_403(self, client: TestClient) -> None:
        outside_path = Path("/etc/passwd")

        with patch("bim.commands.serve._routes.get_repo") as mock_get_repo:
            response = client.get(f"/api/zettels/{outside_path}")

        assert response.status_code == 403
        mock_get_repo.assert_not_called()

    def test_patch_zettel_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"
        outside_path = Path("/etc/passwd")

        with patch("bim.commands.serve._routes.get_repo") as mock_get_repo:
            response = client.patch(
                f"/api/zettels/{outside_path}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_get_repo.assert_not_called()

    def test_patch_zettel_without_token_returns_401(self, client: TestClient, tmp_path: Path) -> None:
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._routes.get_repo") as mock_get_repo:
            response = client.patch(
                f"/api/zettels/{real_file}",
                json={"field": "title", "value": "New Title"},
            )

        assert response.status_code == 401
        mock_get_repo.assert_not_called()

    def test_patch_zettel_with_wrong_token_returns_401(self, client: TestClient, tmp_path: Path) -> None:
        client.app.state.buvis_token = "correct-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._routes.get_repo") as mock_get_repo:
            response = client.patch(
                f"/api/zettels/{real_file}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "wrong-token"},
            )

        assert response.status_code == 401
        mock_get_repo.assert_not_called()

    def test_patch_zettel_success_returns_200_envelope(self, client: TestClient, tmp_path: Path) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(
                success=True,
                output="Updated note.md",
                metadata={"updated_count": 1},
            )

            response = client.patch(
                f"/api/zettels/{real_file}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["output"] == "Updated note.md"
        assert body["metadata"] == {"updated_count": 1}

    def test_patch_zettel_real_repository_persists_metadata_change(
        self, client: TestClient, tmp_path: Path, minimal_zettel: str
    ) -> None:
        """No CommandEditNote mock, no repository mock: drives the route through the
        real MarkdownZettelRepository / UpdateZettelUseCase and asserts the file on
        disk actually changed, proving PATCH delegates to a real persisted update."""
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text(minimal_zettel, encoding="utf-8")

        response = client.patch(
            f"/api/zettels/{real_file}",
            json={"field": "title", "value": "New Title"},
            headers={"X-Buvis-Token": "test-token"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        updated = real_file.read_text(encoding="utf-8")
        assert "title: New Title" in updated
        assert "type: note" in updated
        assert "alpha" in updated
        assert "beta" in updated
        assert "processed: false" in updated
        assert "publish: false" in updated
        assert "Some body text." in updated

    def test_patch_zettel_real_repository_persists_section_change(
        self, client: TestClient, tmp_path: Path, minimal_zettel: str
    ) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text(minimal_zettel, encoding="utf-8")

        # The parser folds body content under a section keyed on the title
        # ("# Original Title"), not the literal "## Content" heading in the
        # fixture, so that's the heading a section-target edit must address.
        response = client.patch(
            f"/api/zettels/{real_file}",
            json={"field": "# Original Title", "value": "New body text.", "target": "section"},
            headers={"X-Buvis-Token": "test-token"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        updated = real_file.read_text(encoding="utf-8")
        assert "New body text." in updated
        assert "Some body text." not in updated
        assert "title: Original Title" in updated

    def test_patch_zettel_missing_returns_404(self, client: TestClient, tmp_path: Path) -> None:
        client.app.state.buvis_token = "test-token"
        missing_file = tmp_path / "zettels" / "missing.md"

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_command:
            response = client.patch(
                f"/api/zettels/{missing_file}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]
        mock_command.assert_not_called()

    def test_patch_zettel_failure_returns_422_envelope(self, client: TestClient, tmp_path: Path) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(
                success=False,
                error="No changes provided",
            )

            response = client.patch(
                f"/api/zettels/{real_file}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "No changes provided"

    def test_get_zettel_missing_returns_404(self, client: TestClient, tmp_path: Path) -> None:
        file_path = tmp_path / "zettels" / "missing.md"
        with patch("pathlib.Path.is_file", return_value=False):
            response = client.get(f"/api/zettels/{file_path}")

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]
