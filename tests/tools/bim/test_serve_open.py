from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from starlette.testclient import TestClient


class TestServeOpen:
    def test_open_file_without_token_returns_401(self, client: TestClient, tmp_path: Path) -> None:
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._routes.open_in_os") as mock_open_in_os:
            response = client.post(
                "/api/open",
                json={"path": str(real_file)},
            )

        assert response.status_code == 401
        mock_open_in_os.assert_not_called()

    def test_open_file_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"
        outside_path = Path("/etc/passwd")

        with patch("bim.commands.serve._routes.open_in_os") as mock_open_in_os:
            response = client.post(
                "/api/open",
                json={"path": str(outside_path)},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_open_in_os.assert_not_called()

    def test_open_file_in_vault_with_valid_token_returns_200_and_opens_resolved_path(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._routes.open_in_os") as mock_open_in_os:
            response = client.post(
                "/api/open",
                json={"path": str(real_file)},
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )

        assert response.status_code == 200
        mock_open_in_os.assert_called_once_with(real_file.resolve())

    def test_open_file_success_returns_full_envelope(self, client: TestClient, tmp_path: Path) -> None:
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._routes.open_in_os"):
            response = client.post(
                "/api/open",
                json={"path": str(real_file)},
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
