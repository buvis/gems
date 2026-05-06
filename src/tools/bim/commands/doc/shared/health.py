from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bim.commands.doc.shared.settings_models import DocSettings

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


def _check_ollama(endpoint: str, primary_model: str) -> None:
    # Lazy import keeps the module loadable without the [doc] extra installed.
    import requests

    url = f"{endpoint.rstrip('/')}/api/tags"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise MissingDependency(f"Ollama daemon not reachable at {endpoint}: {exc}") from exc

    models = payload.get("models") or []
    available = {m.get("name") for m in models if isinstance(m, dict)}
    if primary_model not in available:
        raise MissingDependency(f"Ollama model {primary_model!r} not pulled (run `ollama pull {primary_model}`)")


def check_health(settings: DocSettings) -> None:
    """Validate that all external dependencies are present and reachable.

    Raises MissingDependency on the first missing item.
    """
    _check_binary("tesseract")
    _check_binary("ocrmypdf")
    _check_ollama(settings.classifier.endpoint, settings.classifier.primary_model)
