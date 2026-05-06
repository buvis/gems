"""LLM-backed document classifier (Ollama /api/chat).

Sends OCR text to a local Ollama instance and parses the JSON response into a
``ClassifyResult``. The ``requests`` import is deferred until ``classify`` runs
so the module is loadable without the optional ``[doc]`` extra installed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from bim.commands.doc.shared.issuers import resolve_alias

if TYPE_CHECKING:
    from bim.commands.doc.shared.issuers import IssuerRegistry
    from bim.commands.doc.shared.settings_models import ClassifierSettings

__all__ = ["Classifier", "ClassifierError", "ClassifyResult"]


_REQUEST_TIMEOUT_SECONDS = 60


class ClassifierError(Exception):
    """Raised when the classifier cannot produce a usable result."""


class ClassifyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    issuer_slug: str | None
    issuer_display: str | None
    doc_type: str
    language: str
    confidence: float


def _build_alias_block(registry: IssuerRegistry) -> str:
    lines: list[str] = []
    for slug, entry in registry.issuers.items():
        aliases = ", ".join(entry.aliases) if entry.aliases else "(none)"
        lines.append(f"- {slug} ({entry.display_name}): aliases: {aliases}")
    return "\n".join(lines)


def _full_system_prompt(registry: IssuerRegistry) -> str:
    alias_block = _build_alias_block(registry)
    return (
        "You classify scanned business documents from OCR text.\n"
        "Return STRICT JSON with keys: issuer_slug, doc_type, language, confidence.\n"
        "Use the canonical issuer slug from the list below if you recognize the issuer; "
        "otherwise return your best guess as a short slug.\n"
        "\n"
        "Known issuers (canonical slug, display name, aliases):\n"
        f"{alias_block}\n"
        "\n"
        "Examples:\n"
        '- OCR contains "Faktura č. 12345" from ČEZ -> '
        '{"issuer_slug": "cez-as", "doc_type": "invoice", "language": "cs", "confidence": 0.95}\n'
        '- OCR contains "Vyúčtování služeb" from O2 -> '
        '{"issuer_slug": "o2-czech", "doc_type": "statement", "language": "cs", "confidence": 0.93}\n'
    )


def _doc_type_only_system_prompt() -> str:
    return (
        "You classify scanned business documents from OCR text.\n"
        "Return STRICT JSON with keys: doc_type, language, confidence.\n"
        "Pick doc_type from: invoice, receipt, statement, contract, certificate, "
        "reminder, correspondence, other.\n"
    )


def _user_prompt(ocr_text: str, source_metadata: dict[str, object]) -> str:
    return (
        f"OCR text:\n{ocr_text}\n\nSource metadata: {json.dumps(source_metadata, ensure_ascii=False, sort_keys=True)}\n"
    )


class Classifier:
    """Classify OCR text via an Ollama /api/chat endpoint."""

    def __init__(self, settings: ClassifierSettings) -> None:
        self._settings = settings

    def classify(
        self,
        ocr_text: str,
        source_metadata: dict[str, object],
        registry: IssuerRegistry,
        *,
        doc_type_only: bool = False,
    ) -> ClassifyResult:
        # Lazy import keeps the module loadable without the [doc] extra installed.
        import requests

        url = f"{self._settings.endpoint.rstrip('/')}/api/chat"
        system_prompt = _doc_type_only_system_prompt() if doc_type_only else _full_system_prompt(registry)
        body = {
            "model": self._settings.primary_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _user_prompt(ocr_text, source_metadata)},
            ],
            "format": "json",
            "stream": False,
        }

        try:
            response = requests.post(url, json=body, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.Timeout:
            raise
        except Exception as exc:
            raise ClassifierError(f"HTTP error calling {url}: {exc}") from exc

        try:
            raw_content = payload["message"]["content"]
            parsed = json.loads(raw_content)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ClassifierError(f"Could not parse classifier JSON response: {exc}") from exc

        issuer_slug: str | None = None
        issuer_display: str | None = None
        if not doc_type_only:
            candidate = parsed.get("issuer_slug")
            if isinstance(candidate, str) and candidate:
                canonical = resolve_alias(registry, candidate)
                if canonical is not None:
                    issuer_slug = canonical
                    issuer_display = registry.issuers[canonical].display_name

        return ClassifyResult(
            issuer_slug=issuer_slug,
            issuer_display=issuer_display,
            doc_type=parsed["doc_type"],
            language=parsed["language"],
            confidence=float(parsed["confidence"]),
        )
