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
from bim.commands.doc.shared.naming import slugify
from bim.commands.doc.shared.rules.models import SourceMetadata

if TYPE_CHECKING:
    from bim.commands.doc.shared.issuers import IssuerRegistry
    from bim.commands.doc.shared.settings_models import ClassifierSettings

__all__ = ["Classifier", "ClassifierError", "ClassifyResult"]


_REQUEST_TIMEOUT_SECONDS = 60


class ClassifierError(Exception):
    """Raised when the classifier cannot produce a usable result.

    ``transient`` flags whether retrying the call against the same model is
    likely to help. HTTP-transport failures are transient; JSON parse errors
    and missing-field errors come from the model itself and won't recover
    on retry. The pipeline's retry helper checks this flag to short-circuit
    semantic failures straight to triage instead of burning the full retry
    budget plus the fallback attempt on un-fixable model output.
    """

    def __init__(self, message: str, *, transient: bool = True) -> None:
        super().__init__(message)
        self.transient = transient


class ClassifyResult(BaseModel):
    """Structured classifier output.

    Attributes:
        issuer_slug: Canonical issuer slug from the registry, or ``None`` when
            the model returned an unrecognised slug or the call ran in
            doc-type-only mode.
        issuer_display: Human-readable issuer name from the registry, paired
            with ``issuer_slug``.
        issuer_guess: Slugified form of the model's raw issuer suggestion when
            it did NOT resolve to a registry entry, otherwise ``None``. Used by
            the pipeline to pre-fill the triage proposal so a human can review
            the guess and decide whether to register it as a new issuer.
        doc_type: One of the canonical document types (invoice, receipt,
            statement, contract, certificate, reminder, correspondence, other).
        language: ISO 639-1 language code reported by the model (e.g. ``cs``).
        confidence: Model self-reported confidence in [0.0, 1.0].
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    issuer_slug: str | None
    issuer_display: str | None
    doc_type: str
    language: str
    confidence: float
    issuer_guess: str | None = None


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


def _reduced_system_prompt(registry: IssuerRegistry, *, omit: set[str]) -> str:
    fields = [field for field in ("issuer_slug", "doc_type", "language", "confidence") if field not in omit]
    lines = [
        "You classify scanned business documents from OCR text.",
        f"Return STRICT JSON with keys: {', '.join(fields)}.",
    ]
    if "doc_type" in fields:
        lines.append(
            "Pick doc_type from: invoice, receipt, statement, contract, certificate, reminder, correspondence, other."
        )
    if "issuer_slug" in fields:
        alias_block = _build_alias_block(registry)
        lines.extend(
            [
                "Use the canonical issuer slug from the list below if you recognize the issuer; "
                "otherwise return your best guess as a short slug.",
                "",
                "Known issuers (canonical slug, display name, aliases):",
                alias_block,
            ]
        )
    return "\n".join(lines) + "\n"


def _source_metadata_to_prompt_dict(metadata: SourceMetadata, *, doc_type_only: bool) -> dict[str, object]:
    """Project ``SourceMetadata`` to the JSON shape the user prompt embeds.

    The legacy contract emitted ``source`` (not ``source_kind``) and only
    populated keys whose values were truthy. ``doc_type_only`` mode (used
    by the issuer-inbox path) further omits issuer-related hints
    (``original_filename``, ``email_from``, ``email_subject``) so the
    prompt stays focused on doc-type and cannot leak the pinned issuer
    back into the LLM. ``email_date`` is intentionally also omitted: it
    feeds the rule engine but never enters the classifier prompt.
    """
    payload: dict[str, object] = {"source": metadata.source_kind}
    if doc_type_only:
        return payload
    if metadata.original_filename:
        payload["original_filename"] = metadata.original_filename
    if metadata.email_from:
        payload["email_from"] = metadata.email_from
    if metadata.email_subject:
        payload["email_subject"] = metadata.email_subject
    return payload


def _user_prompt(ocr_text: str, source_metadata: SourceMetadata, *, doc_type_only: bool) -> str:
    payload = _source_metadata_to_prompt_dict(source_metadata, doc_type_only=doc_type_only)
    return f"OCR text:\n{ocr_text}\n\nSource metadata: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n"


def _pinned_language(pinned: dict[str, object]) -> object:
    return pinned.get("language") if pinned.get("language") is not None else pinned.get("doc_language")


def _omit_set(pinned_slug: object, pinned_type: object, pinned_lang: object) -> set[str]:
    omit: set[str] = set()
    if pinned_slug is not None:
        omit.add("issuer_slug")
    if pinned_type is not None:
        omit.add("doc_type")
    if pinned_lang is not None:
        omit.add("language")
    return omit


def _pinned_display(pinned: dict[str, object], slug: str, registry: IssuerRegistry) -> str | None:
    pinned_display = pinned.get("issuer_display")
    if pinned_display:
        return str(pinned_display)
    if slug in registry.issuers:
        return registry.issuers[slug].display_name
    return None


def _full_skip_result(
    pinned: dict[str, object],
    pinned_slug: object,
    pinned_type: object,
    pinned_lang: object,
    registry: IssuerRegistry,
) -> ClassifyResult:
    slug = str(pinned_slug)
    return ClassifyResult(
        issuer_slug=slug,
        issuer_display=_pinned_display(pinned, slug, registry),
        doc_type=str(pinned_type),
        language=str(pinned_lang),
        confidence=1.0,
        issuer_guess=None,
    )


def _resolve_pinned_issuer(
    pinned_slug: object, pinned_display: object, registry: IssuerRegistry
) -> tuple[str, str | None, None]:
    slug = str(pinned_slug)
    if pinned_display:
        display: str | None = str(pinned_display)
    elif slug in registry.issuers:
        display = registry.issuers[slug].display_name
    else:
        display = None
    return slug, display, None


def _resolve_model_issuer(
    parsed: dict[str, object], registry: IssuerRegistry
) -> tuple[str | None, str | None, str | None]:
    candidate = parsed.get("issuer_slug")
    if not isinstance(candidate, str) or not candidate:
        return None, None, None
    canonical = resolve_alias(registry, candidate)
    if canonical is not None:
        return canonical, registry.issuers[canonical].display_name, None
    try:
        return None, None, slugify(candidate)
    except ValueError:
        return None, None, None


def _resolve_classified_issuer(
    pinned_slug: object,
    pinned_display: object,
    parsed: dict[str, object],
    registry: IssuerRegistry,
) -> tuple[str | None, str | None, str | None]:
    if pinned_slug is not None:
        return _resolve_pinned_issuer(pinned_slug, pinned_display, registry)
    return _resolve_model_issuer(parsed, registry)


def _coerce_confidence(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        raise ClassifierError(
            f"could not parse classifier field: confidence has unexpected type {type(raw).__name__}",
            transient=False,
        )
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ClassifierError(f"could not parse classifier field: {exc}", transient=False) from exc


def _resolve_classified_payload(
    parsed: dict[str, object], *, pinned_type: object, pinned_lang: object
) -> tuple[str, str, float]:
    if pinned_type is not None:
        doc_type: object = pinned_type
    elif "doc_type" in parsed:
        doc_type = parsed["doc_type"]
    else:
        raise ClassifierError("missing field 'doc_type' in model response", transient=False)

    if pinned_lang is not None:
        language: object = pinned_lang
    elif "language" in parsed:
        language = parsed["language"]
    else:
        raise ClassifierError("missing field 'language' in model response", transient=False)

    if "confidence" not in parsed:
        raise ClassifierError("missing field 'confidence' in model response", transient=False)
    confidence = _coerce_confidence(parsed["confidence"])
    return str(doc_type), str(language), confidence


class Classifier:
    """Classify OCR text via an Ollama /api/chat endpoint."""

    def __init__(self, settings: ClassifierSettings) -> None:
        self._settings = settings

    def classify(
        self,
        ocr_text: str,
        source_metadata: SourceMetadata,
        registry: IssuerRegistry,
        *,
        doc_type_only: bool = False,
    ) -> ClassifyResult:
        """Classify a document from OCR text via the configured Ollama endpoint.

        Thin shim that forwards to :meth:`classify_with_model` using the
        configured primary model. Kept for callers that don't need to
        substitute the model (e.g. ad-hoc usage outside the retry pipeline).
        """
        return self.classify_with_model(
            ocr_text,
            source_metadata,
            registry,
            model=self._settings.primary_model,
            doc_type_only=doc_type_only,
        )

    def classify_with_model(
        self,
        ocr_text: str,
        source_metadata: SourceMetadata,
        registry: IssuerRegistry,
        *,
        model: str,
        doc_type_only: bool = False,
    ) -> ClassifyResult:
        """Like :meth:`classify` but the caller picks the Ollama model name.

        Used by the pipeline's retry helper to substitute ``fallback_model``
        for ``primary_model`` after exhausted retries.

        Raises:
            ClassifierError: HTTP transport failed, response was not parseable
                JSON, or required fields were missing/uncoercible.
            requests.exceptions.Timeout: Re-raised unwrapped so callers can
                distinguish slow-LLM scenarios from other failures.
        """
        # Lazy import keeps the module loadable without the [doc] extra installed.
        import requests

        url = f"{self._settings.endpoint.rstrip('/')}/api/chat"
        system_prompt = _doc_type_only_system_prompt() if doc_type_only else _full_system_prompt(registry)
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _user_prompt(ocr_text, source_metadata, doc_type_only=doc_type_only)},
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
            # HTTP / network failure; retrying may succeed.
            raise ClassifierError(f"HTTP error calling {url}: {exc}", transient=True) from exc

        try:
            raw_content = payload["message"]["content"]
            parsed = json.loads(raw_content)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            # Model produced unparseable output; another attempt against the
            # same model is unlikely to help.
            raise ClassifierError(f"Could not parse classifier JSON response: {exc}", transient=False) from exc

        issuer_slug: str | None = None
        issuer_display: str | None = None
        issuer_guess: str | None = None
        if not doc_type_only:
            candidate = parsed.get("issuer_slug")
            if isinstance(candidate, str) and candidate:
                canonical = resolve_alias(registry, candidate)
                if canonical is not None:
                    issuer_slug = canonical
                    issuer_display = registry.issuers[canonical].display_name
                else:
                    # Preserve the model's raw suggestion so the pipeline can
                    # pre-fill the triage proposal. Slugify enforces the same
                    # kebab-case shape as registry slugs; if normalisation
                    # collapses to empty, fall through with issuer_guess=None.
                    try:
                        issuer_guess = slugify(candidate)
                    except ValueError:
                        issuer_guess = None

        try:
            doc_type = parsed["doc_type"]
            language = parsed["language"]
            confidence = float(parsed["confidence"])
        except KeyError as exc:
            raise ClassifierError(f"missing field {exc.args[0]!r} in model response", transient=False) from exc
        except (TypeError, ValueError) as exc:
            raise ClassifierError(f"could not parse classifier field: {exc}", transient=False) from exc

        return ClassifyResult(
            issuer_slug=issuer_slug,
            issuer_display=issuer_display,
            doc_type=doc_type,
            language=language,
            confidence=confidence,
            issuer_guess=issuer_guess,
        )

    def classify_with_pinned(
        self,
        ocr_text: str,
        source_metadata: SourceMetadata,
        registry: IssuerRegistry,
        pinned: dict[str, object],
        *,
        model: str,
    ) -> ClassifyResult:
        """Classify with some classifier fields pre-pinned by the rule engine.

        Skips the LLM entirely if ``pinned`` covers all of ``issuer_slug``,
        ``doc_type``, and ``language``. Otherwise asks the model only for the
        missing fields, then lets pinned values override model output.
        """
        pinned_slug = pinned.get("issuer_slug")
        pinned_type = pinned.get("doc_type")
        pinned_lang = _pinned_language(pinned)

        if pinned_slug is not None and pinned_type is not None and pinned_lang is not None:
            return _full_skip_result(pinned, pinned_slug, pinned_type, pinned_lang, registry)

        omit = _omit_set(pinned_slug, pinned_type, pinned_lang)
        parsed = self._call_chat(ocr_text, source_metadata, registry, model=model, omit=omit)

        issuer_slug, issuer_display, issuer_guess = _resolve_classified_issuer(
            pinned_slug, pinned.get("issuer_display"), parsed, registry
        )
        doc_type, language, confidence = _resolve_classified_payload(
            parsed, pinned_type=pinned_type, pinned_lang=pinned_lang
        )
        return ClassifyResult(
            issuer_slug=issuer_slug,
            issuer_display=issuer_display,
            doc_type=doc_type,
            language=language,
            confidence=confidence,
            issuer_guess=issuer_guess,
        )

    def _call_chat(
        self,
        ocr_text: str,
        source_metadata: SourceMetadata,
        registry: IssuerRegistry,
        *,
        model: str,
        omit: set[str],
    ) -> dict[str, object]:
        """Send the reduced-prompt request and parse the JSON content."""
        # Lazy import keeps the module loadable without the [doc] extra installed.
        import requests

        url = f"{self._settings.endpoint.rstrip('/')}/api/chat"
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": _reduced_system_prompt(registry, omit=omit)},
                {"role": "user", "content": _user_prompt(ocr_text, source_metadata, doc_type_only=False)},
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
            raise ClassifierError(f"HTTP error calling {url}: {exc}", transient=True) from exc

        try:
            raw_content = payload["message"]["content"]
            parsed = json.loads(raw_content)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ClassifierError(f"Could not parse classifier JSON response: {exc}", transient=False) from exc
        if not isinstance(parsed, dict):
            raise ClassifierError("classifier response is not a JSON object", transient=False)
        return parsed
