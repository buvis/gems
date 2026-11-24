from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bim.commands.doc.shared.health import MissingDependency, check_health
from bim.commands.doc.shared.settings_models import ClassifierSettings, DocPaths, DocSettings
from bim.shared.llm import ClaudeBackendSettings, CommandBackendSettings, HttpBackendSettings, LLMConfigError
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


class TestLlamacppBackend:
    @pytest.fixture
    def llamacpp_settings(self, settings: DocSettings) -> DocSettings:
        classifier = settings.classifier.model_copy(update={"backend": "llamacpp", "endpoint": "http://localhost:8002"})
        return settings.model_copy(update={"classifier": classifier})

    def test_probes_v1_models_without_model_check(self, llamacpp_settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        fake_requests = mocker.MagicMock()
        fake_requests.get.return_value = _MockResponse({"data": [{"id": "whatever-is-loaded"}]})
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        check_health(llamacpp_settings)

        assert fake_requests.get.call_args.args[0] == "http://localhost:8002/v1/models"

    def test_unreachable_names_llamacpp(self, llamacpp_settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        fake_requests = mocker.MagicMock()
        fake_requests.get.side_effect = ConnectionError("refused")
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(MissingDependency, match="llama.cpp server not reachable"):
            check_health(llamacpp_settings)


FAST = HttpBackendSettings(kind="ollama", endpoint="http://fast:11434", model="m-fast")
SLOW = HttpBackendSettings(kind="llamacpp", endpoint="http://slow:8002")


def _named(settings: DocSettings, backend: str, fallback: str | None = None) -> DocSettings:
    return settings.model_copy(update={"classifier": ClassifierSettings(backend=backend, fallback=fallback)})


def _patch_requests(mocker: MockerFixture, replies: dict[str, object]) -> MagicMock:
    """Serve ``replies[url]``; an Exception value is raised as the transport failure."""

    def fake_get(url: str, *args: object, **kwargs: object) -> object:
        reply = replies[url]
        if isinstance(reply, Exception):
            raise reply
        return reply

    fake_requests = mocker.MagicMock()
    fake_requests.get.side_effect = fake_get
    mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)
    return fake_requests


def _patch_which(mocker: MockerFixture, on_path: set[str]) -> list[str]:
    """Answer ``shutil.which`` from ``on_path`` by exact name; return the names asked for."""
    asked: list[str] = []

    def fake_which(name: str, *args: object, **kwargs: object) -> str | None:
        asked.append(name)
        return f"/usr/bin/{name}" if name in on_path else None

    mocker.patch("shutil.which", side_effect=fake_which)
    return asked


def _urls(fake_requests: MagicMock) -> list[str]:
    return [call.args[0] for call in fake_requests.get.call_args_list]


class TestLegacyChecksPrimaryOnce:
    @pytest.mark.parametrize("llm", [None, {}], ids=["llm-none", "llm-empty"])
    def test_defaults_probe_only_the_primary_model(
        self, settings: DocSettings, mocker: MockerFixture, llm: dict[str, HttpBackendSettings] | None
    ) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        # The fallback model qwen3:14b is not pulled: legacy health never checked it.
        tags = _MockResponse({"models": [{"name": "qwen3:30b-a3b"}]})
        fake_requests = _patch_requests(mocker, {"http://localhost:11434/api/tags": tags})

        check_health(settings, llm)

        assert _urls(fake_requests) == ["http://localhost:11434/api/tags"]


class TestNamedHttpBackends:
    def test_distinct_primary_and_fallback_are_both_probed_in_order(
        self, settings: DocSettings, mocker: MockerFixture
    ) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        fake_requests = _patch_requests(
            mocker,
            {
                "http://fast:11434/api/tags": _MockResponse({"models": [{"name": "m-fast"}]}),
                "http://slow:8002/v1/models": _MockResponse({"data": []}),
            },
        )

        check_health(_named(settings, "fast", "slow"), {"fast": FAST, "slow": SLOW})

        assert _urls(fake_requests) == ["http://fast:11434/api/tags", "http://slow:8002/v1/models"]

    def test_unreachable_fallback_raises(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        _patch_requests(
            mocker,
            {
                "http://fast:11434/api/tags": _MockResponse({"models": [{"name": "m-fast"}]}),
                "http://slow:8002/v1/models": ConnectionError("refused"),
            },
        )

        with pytest.raises(MissingDependency, match="llama.cpp server not reachable at http://slow:8002"):
            check_health(_named(settings, "fast", "slow"), {"fast": FAST, "slow": SLOW})

    def test_same_backend_as_fallback_is_probed_once(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        tags = _MockResponse({"models": [{"name": "m-fast"}]})
        fake_requests = _patch_requests(mocker, {"http://fast:11434/api/tags": tags})

        check_health(_named(settings, "fast"), {"fast": FAST, "slow": SLOW})

        assert _urls(fake_requests) == ["http://fast:11434/api/tags"]

    def test_ollama_entry_model_must_be_pulled_exactly(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        tags = _MockResponse({"models": [{"name": "m-fast-q4"}]})
        _patch_requests(mocker, {"http://fast:11434/api/tags": tags})

        with pytest.raises(MissingDependency, match="Ollama model 'm-fast' not pulled"):
            check_health(_named(settings, "fast"), {"fast": FAST})

    def test_ollama_entry_without_model_skips_pulled_check(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        bare = HttpBackendSettings(kind="ollama", endpoint="http://bare:11434")
        fake_requests = _patch_requests(mocker, {"http://bare:11434/api/tags": _MockResponse({"models": []})})

        check_health(_named(settings, "bare"), {"bare": bare})

        assert _urls(fake_requests) == ["http://bare:11434/api/tags"]

    def test_openai_probes_v1_models(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        oa = HttpBackendSettings(kind="openai", endpoint="http://oa:9000", model="gpt-x")
        fake_requests = _patch_requests(mocker, {"http://oa:9000/v1/models": _MockResponse({"data": []})})

        check_health(_named(settings, "oa"), {"oa": oa})

        assert _urls(fake_requests) == ["http://oa:9000/v1/models"]

    def test_openai_unreachable_names_openai_compatible_server(
        self, settings: DocSettings, mocker: MockerFixture
    ) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        oa = HttpBackendSettings(kind="openai", endpoint="http://oa:9000")
        _patch_requests(mocker, {"http://oa:9000/v1/models": ConnectionError("refused")})

        with pytest.raises(MissingDependency, match="OpenAI-compatible server") as excinfo:
            check_health(_named(settings, "oa"), {"oa": oa})
        assert "llama.cpp" not in str(excinfo.value)

    def test_named_mode_still_checks_tesseract_before_any_probe(
        self, settings: DocSettings, mocker: MockerFixture
    ) -> None:
        mocker.patch(
            "bim.commands.doc.shared.health.subprocess.run",
            side_effect=FileNotFoundError("tesseract not found"),
        )
        tags = _MockResponse({"models": [{"name": "m-fast"}]})
        fake_requests = _patch_requests(mocker, {"http://fast:11434/api/tags": tags})

        with pytest.raises(MissingDependency, match="tesseract"):
            check_health(_named(settings, "fast"), {"fast": FAST})
        assert _urls(fake_requests) == []

    def test_unknown_backend_name_raises_config_error(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        fake_requests = _patch_requests(mocker, {})

        with pytest.raises(LLMConfigError):
            check_health(_named(settings, "fas"), {"fast": FAST, "slow": SLOW})
        assert _urls(fake_requests) == []

    def test_ollama_fallback_model_must_be_pulled(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        fb = HttpBackendSettings(kind="ollama", endpoint="http://fb:11434", model="m-fb")
        _patch_requests(
            mocker,
            {
                "http://slow:8002/v1/models": _MockResponse({"data": []}),
                "http://fb:11434/api/tags": _MockResponse({"models": [{"name": "m-fast"}]}),
            },
        )

        with pytest.raises(MissingDependency, match="Ollama model 'm-fb' not pulled"):
            check_health(_named(settings, "slow", "fb"), {"slow": SLOW, "fb": fb})

    def test_named_ollama_unreachable_names_its_endpoint(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        _patch_requests(mocker, {"http://fast:11434/api/tags": ConnectionError("refused")})

        with pytest.raises(MissingDependency, match="Ollama daemon not reachable at http://fast:11434"):
            check_health(_named(settings, "fast"), {"fast": FAST})


class TestNamedLocalBackends:
    def test_claude_on_path_passes_without_http(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        fake_requests = _patch_requests(mocker, {})
        asked = _patch_which(mocker, {"claude"})

        check_health(_named(settings, "cl"), {"cl": ClaudeBackendSettings(kind="claude")})

        assert asked == ["claude"]
        assert _urls(fake_requests) == []

    def test_claude_missing_raises(self, settings: DocSettings, mocker: MockerFixture) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        _patch_which(mocker, {"claude-code"})

        with pytest.raises(MissingDependency, match="^claude not found on PATH$"):
            check_health(_named(settings, "cl"), {"cl": ClaudeBackendSettings(kind="claude")})

    @pytest.mark.parametrize("argv", [["my-llm", "--json"], ["run-model", "-q", "x"]])
    def test_command_on_path_checks_argv0(self, settings: DocSettings, mocker: MockerFixture, argv: list[str]) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        asked = _patch_which(mocker, {argv[0]})

        check_health(_named(settings, "cmd"), {"cmd": CommandBackendSettings(kind="command", argv=argv)})

        assert asked == [argv[0]]

    @pytest.mark.parametrize("argv", [["my-llm", "--json"], ["run-model", "-q", "x"]])
    def test_command_missing_raises_with_argv0(
        self, settings: DocSettings, mocker: MockerFixture, argv: list[str]
    ) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        _patch_which(mocker, {f"{argv[0]}-other", *argv[1:]})

        with pytest.raises(MissingDependency, match=f"^{argv[0]} not found on PATH$"):
            check_health(_named(settings, "cmd"), {"cmd": CommandBackendSettings(kind="command", argv=argv)})

    def test_missing_command_fallback_raises_after_claude_primary(
        self, settings: DocSettings, mocker: MockerFixture
    ) -> None:
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=_ok_proc())
        asked = _patch_which(mocker, {"claude"})
        llm = {
            "cl": ClaudeBackendSettings(kind="claude"),
            "cmd": CommandBackendSettings(kind="command", argv=["my-llm"]),
        }

        with pytest.raises(MissingDependency, match="^my-llm not found on PATH$"):
            check_health(_named(settings, "cl", "cmd"), llm)
        assert asked == ["claude", "my-llm"]


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
