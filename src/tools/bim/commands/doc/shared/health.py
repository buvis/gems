from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from bim.commands.doc.shared.settings_models import DocSettings
    from bim.shared.llm import ClaudeBackendSettings, CommandBackendSettings, HttpBackendSettings

__all__ = ["MissingDependency", "check_health"]


class MissingDependency(Exception):
    """Raised when a required external dependency is missing or unreachable."""


_VERSION_FLAGS: tuple[str, ...] = ("--version", "-V", "version")


def _check_binary(binary: str) -> None:
    # ``last_stderr`` is initialised so the final ``raise`` cannot reference
    # an unbound name even if ``_VERSION_FLAGS`` is ever made empty by a
    # future refactor; type checkers stop warning about possibly-unbound
    # access too.
    last_stderr = ""
    for flag in _VERSION_FLAGS:
        try:
            result = subprocess.run(
                [binary, flag],
                capture_output=True,
                check=False,
                timeout=5,
            )
        except FileNotFoundError as exc:
            raise MissingDependency(f"{binary} not found on PATH") from exc

        if result.returncode == 0:
            return
        last_stderr = result.stderr.decode(errors="replace").strip()

    raise MissingDependency(f"{binary} version probe failed (tried {list(_VERSION_FLAGS)}): {last_stderr}")


def _check_ollama(endpoint: str, primary_model: str | None) -> None:
    # Lazy import keeps the module loadable without the [doc] extra installed.
    import requests

    url = f"{endpoint.rstrip('/')}/api/tags"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise MissingDependency(f"Ollama daemon not reachable at {endpoint}: {exc}") from exc

    if primary_model is None:
        return
    models = payload.get("models") or []
    available = {m.get("name") for m in models if isinstance(m, dict)}
    if primary_model not in available:
        raise MissingDependency(f"Ollama model {primary_model!r} not pulled (run `ollama pull {primary_model}`)")


def _check_llamacpp(endpoint: str, server: str) -> None:
    # No model check: llama-server serves the one model it was started with
    # and ignores the request's ``model`` field.
    import requests

    url = f"{endpoint.rstrip('/')}/v1/models"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        response.json()
    except Exception as exc:
        raise MissingDependency(f"{server} not reachable at {endpoint}: {exc}") from exc


def _check_on_path(executable: str) -> None:
    if shutil.which(executable) is None:
        raise MissingDependency(f"{executable} not found on PATH")


def _check_backend(
    entry: ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings, model: str | None
) -> None:
    if entry.kind == "claude":
        _check_on_path("claude")
    elif entry.kind == "command":
        _check_on_path(entry.argv[0])
    elif entry.kind == "ollama":
        _check_ollama(entry.endpoint, model or entry.model)
    else:
        _check_llamacpp(entry.endpoint, "OpenAI-compatible server" if entry.kind == "openai" else "llama.cpp server")


def check_health(
    settings: DocSettings,
    llm: Mapping[str, ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings] | None = None,
) -> None:
    """Validate that all external dependencies are present and reachable.

    Checks the OCR binaries, then each distinct backend of the doc LLM route
    (primary first, then fallback).

    Raises:
        MissingDependency: On the first missing item.
        LLMConfigError: When ``doc.classifier`` names an unknown backend.
    """
    from bim.commands.doc.shared.llm import resolve_doc_route

    _check_binary("tesseract")
    _check_binary("ocrmypdf")
    route = resolve_doc_route(settings.classifier, llm or {})
    checked: set[str] = set()
    for target in (route.primary, route.fallback):
        if target.backend not in checked:
            checked.add(target.backend)
            _check_backend(route.backends[target.backend], target.model)
