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
        fake_requests.get.return_value = _MockResponse({"models": [{"name": "qwen3:30b-a3b"}]})
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
        with pytest.raises(MissingDependency, match="qwen3:30b-a3b"):
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

        # Save original so we can restore it after; otherwise the reloaded
        # module's MissingDependency class diverges from the one imported at
        # the top of this file, breaking pytest.raises(MissingDependency, ...)
        # in subsequent tests.
        original_module = sys.modules.get("bim.commands.doc.shared.health")

        try:
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
        finally:
            if original_module is not None:
                sys.modules["bim.commands.doc.shared.health"] = original_module


class TestCheckBinaryFlagFallback:
    """_check_binary tries --version, then -V, then 'version'."""

    def test_dash_version_succeeds_first(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.health import _check_binary

        seen_flags: list[str] = []

        def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            seen_flags.append(argv[1])
            return _ok_proc()

        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            side_effect=fake_run,
        )
        _check_binary("foo")
        assert seen_flags == ["--version"]

    def test_falls_back_to_dash_v(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.health import _check_binary

        seen: list[str] = []

        def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            seen.append(argv[1])
            if argv[1] == "--version":
                return subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"unknown")
            return _ok_proc()

        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            side_effect=fake_run,
        )
        _check_binary("foo")
        assert seen == ["--version", "-V"]

    def test_falls_back_to_bare_version(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.health import _check_binary

        seen: list[str] = []

        def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            seen.append(argv[1])
            if argv[1] in ("--version", "-V"):
                return subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"unknown")
            return _ok_proc()

        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            side_effect=fake_run,
        )
        _check_binary("foo")
        assert seen == ["--version", "-V", "version"]

    def test_all_flags_fail_raises_missing(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.health import _check_binary

        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=2, stdout=b"", stderr=b"nope"),
        )
        with pytest.raises(MissingDependency, match="foo"):
            _check_binary("foo")

    def test_file_not_found_raises_missing(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.health import _check_binary

        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            side_effect=FileNotFoundError("foo"),
        )
        with pytest.raises(MissingDependency, match="not found"):
            _check_binary("foo")
