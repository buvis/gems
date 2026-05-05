from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from bim.commands.doc.shared.health import MissingDependency, check_health
from bim.commands.doc.shared.settings_models import DocPaths, DocSettings
from pytest_mock import MockerFixture


@pytest.fixture
def settings(tmp_path: Path) -> DocSettings:
    paths = DocPaths.model_validate(
        {
            "business_root": str(tmp_path / "Business"),
            "vault_root": str(tmp_path / "Vault"),
        }
    )
    return DocSettings(paths=paths)


def _ok_proc() -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")


class _MockResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class TestCheckHealth:
    def test_happy_path(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            return_value=_ok_proc(),
        )
        fake_requests = mocker.MagicMock()
        fake_requests.get.return_value = _MockResponse({"models": [{"name": "qwen2.5:7b-instruct"}]})
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)
        check_health(settings)  # should not raise

    def test_tesseract_missing_file_not_found(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            side_effect=FileNotFoundError("tesseract not found"),
        )
        with pytest.raises(MissingDependency, match="tesseract"):
            check_health(settings)

    def test_ocrmypdf_returncode_nonzero(self, settings: DocSettings, mocker: MockerFixture) -> None:
        calls = {"n": 0}

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            calls["n"] += 1
            if calls["n"] == 1:
                return _ok_proc()  # tesseract OK
            return subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"ocrmypdf failure")

        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            side_effect=fake_run,
        )
        with pytest.raises(MissingDependency, match="ocrmypdf"):
            check_health(settings)

    def test_ollama_unreachable(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            return_value=_ok_proc(),
        )
        fake_requests = mocker.MagicMock()
        fake_requests.get.side_effect = ConnectionError("refused")
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)
        with pytest.raises(MissingDependency, match="Ollama"):
            check_health(settings)

    def test_ollama_model_not_pulled(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            return_value=_ok_proc(),
        )
        fake_requests = mocker.MagicMock()
        fake_requests.get.return_value = _MockResponse({"models": [{"name": "some-other-model"}]})
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)
        with pytest.raises(MissingDependency, match="qwen2.5:7b-instruct"):
            check_health(settings)

    def test_ollama_non_json_response_wrapped(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            return_value=_ok_proc(),
        )

        class _BadJsonResponse:
            status_code = 200

            def json(self) -> dict[str, object]:
                raise ValueError("not json")

            def raise_for_status(self) -> None:
                return None

        fake_requests = mocker.MagicMock()
        fake_requests.get.return_value = _BadJsonResponse()
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)
        with pytest.raises(MissingDependency, match="Ollama"):
            check_health(settings)


class TestLazyImport:
    def test_module_imports_without_requests_at_module_load(self, mocker: MockerFixture) -> None:
        import builtins
        import importlib
        import sys

        for mod in list(sys.modules):
            if mod == "bim.commands.doc.shared.health":
                del sys.modules[mod]

        real_import = builtins.__import__

        def fake_import(
            name: str,
            globals_: object = None,
            locals_: object = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if name == "requests":
                raise ModuleNotFoundError("requests pretend-missing")
            return real_import(name, globals_, locals_, fromlist, level)

        mocker.patch("builtins.__import__", side_effect=fake_import)
        # Module-level import must succeed without requests installed
        importlib.import_module("bim.commands.doc.shared.health")
