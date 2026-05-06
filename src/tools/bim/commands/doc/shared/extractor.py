"""LLM-backed structured field extractor (Ollama /api/chat).

Sends OCR text plus the already-determined ``doc_type`` to a local Ollama
instance and parses the JSON response into an ``ExtractResult``. The
``requests`` import is deferred until ``extract`` runs so the module is
loadable without the optional ``[doc]`` extra installed.
"""

from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from bim.commands.doc.shared.naming import DOC_TYPES

if TYPE_CHECKING:
    from bim.commands.doc.shared.settings_models import LLMSettings

__all__ = ["ExtractResult", "Extractor", "IncompleteExtraction"]


_REQUEST_TIMEOUT_SECONDS = 60

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "invoice": ("number", "date", "amount", "currency"),
    "statement": ("period_start", "period_end", "balance", "currency"),
    "contract": ("counterparty", "effective_date"),
    "receipt": ("vendor", "date", "amount", "currency"),
    "certificate": ("subject", "issued_date"),
    "correspondence": ("subject", "date"),
    "reminder": ("subject", "date"),
    "other": ("title", "date"),
}

_DATE_FIELDS: frozenset[str] = frozenset(
    {
        "date",
        "payment_due_date",
        "period_start",
        "period_end",
        "effective_date",
        "signed_date",
        "issued_date",
        "expires_date",
    }
)

_NUMERIC_FIELDS: frozenset[str] = frozenset({"amount", "balance"})


class IncompleteExtraction(Exception):
    """Raised when the extractor cannot produce a complete, usable result.

    The ``transient`` flag distinguishes HTTP/transport failures (retryable)
    from semantic failures like missing fields or uncoercible values
    (not retryable - the model's output is fundamentally unusable for this
    document, retrying with the same input won't help).
    """

    def __init__(self, reasons: list[str], *, transient: bool = False) -> None:
        """Initialise with one or more reasons describing why extraction failed.

        Args:
            reasons: Human-readable failure reasons. Joined with ``"; "`` to
                form the exception message and exposed as ``self.reasons`` for
                callers that want to inspect them individually.
            transient: True when the failure is HTTP/transport-related (the
                model server was unreachable or returned an HTTP error) and a
                retry might succeed. False (default) when the failure is
                semantic - missing required fields, uncoercible values, or
                unparseable model output. Only transient failures should be
                retried.
        """
        super().__init__("; ".join(reasons))
        self.reasons = reasons
        self.transient = transient


class ExtractResult(BaseModel):
    """Structured extractor output.

    All fields except ``doc_type`` are optional and populated only when the
    underlying model returned a coercible value. Required fields are enforced
    per ``doc_type`` via ``_REQUIRED_FIELDS`` and an
    :class:`IncompleteExtraction` is raised when any are missing.

    Dates are stored as :class:`datetime.date`; numeric fields (``amount``,
    ``balance``) are coerced to :class:`float`. The model is frozen and
    forbids extras to keep the on-disk frontmatter shape stable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_type: str
    number: str | None = None
    date: datetime.date | None = None
    amount: float | None = None
    currency: str | None = None
    period: str | None = None
    payment_due_date: datetime.date | None = None
    period_start: datetime.date | None = None
    period_end: datetime.date | None = None
    balance: float | None = None
    counterparty: str | None = None
    effective_date: datetime.date | None = None
    term: str | None = None
    signed_date: datetime.date | None = None
    vendor: str | None = None
    subject: str | None = None
    issued_date: datetime.date | None = None
    expires_date: datetime.date | None = None
    title: str | None = None


def _system_prompt(doc_type: str) -> str:
    required = ", ".join(_REQUIRED_FIELDS[doc_type])
    return (
        "You extract structured fields from scanned business documents from OCR text.\n"
        f"The document type is: {doc_type}.\n"
        f"Return STRICT JSON. For doc_type {doc_type}, required fields are: {required}.\n"
        "Use ISO 8601 dates (YYYY-MM-DD). Use numeric values (no currency symbols) for "
        "amount and balance. If a field is unknown, omit it or set it to null.\n"
    )


def _user_prompt(ocr_text: str) -> str:
    return f"OCR text:\n{ocr_text}\n"


def _coerce_date(name: str, value: object) -> datetime.date:
    if not isinstance(value, str) or not value:
        raise IncompleteExtraction([f"could not coerce date '{value}' for field {name}"])
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise IncompleteExtraction([f"could not coerce date '{value}' for field {name}: {exc}"]) from exc


def _coerce_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise IncompleteExtraction([f"could not coerce number '{value}' for field {name}"])
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise IncompleteExtraction([f"could not coerce number '{value}' for field {name}: {exc}"]) from exc


class Extractor:
    """Extract structured fields from OCR text via an Ollama /api/chat endpoint."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings

    def extract(self, ocr_text: str, doc_type: str) -> ExtractResult:
        """Extract structured fields for ``doc_type`` from OCR text via Ollama.

        Args:
            ocr_text: OCR text extracted from the source document.
            doc_type: Canonical document type (one of :data:`DOC_TYPES`) used
                to pick the required-field set and shape the system prompt.

        Returns:
            A populated :class:`ExtractResult` with all required fields for
            ``doc_type`` and any optional fields the model returned.

        Raises:
            ValueError: ``doc_type`` is not one of the canonical types.
            IncompleteExtraction: HTTP transport failed, the response was not
                parseable JSON, the response was not a JSON object, a value
                could not be coerced (e.g. non-ISO date, non-numeric amount),
                or one or more required fields were missing.
            requests.exceptions.Timeout: Re-raised unwrapped so callers can
                distinguish slow-LLM scenarios from other failures.
        """
        if doc_type not in DOC_TYPES:
            raise ValueError(f"doc_type must be one of {DOC_TYPES}, got {doc_type!r}")

        # Lazy import keeps the module loadable without the [doc] extra installed.
        import requests

        url = f"{self._settings.endpoint.rstrip('/')}/api/chat"
        body = {
            "model": self._settings.primary_model,
            "messages": [
                {"role": "system", "content": _system_prompt(doc_type)},
                {"role": "user", "content": _user_prompt(ocr_text)},
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
            # Transport-layer failure - retry against primary or fall back.
            raise IncompleteExtraction([f"HTTP error: {exc}"], transient=True) from exc

        try:
            raw_content = payload["message"]["content"]
            parsed = json.loads(raw_content)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise IncompleteExtraction([f"could not parse model response as JSON: {exc}"]) from exc

        if not isinstance(parsed, dict):
            raise IncompleteExtraction(["could not parse model response as JSON: not an object"])

        allowed_fields = set(ExtractResult.model_fields.keys()) - {"doc_type"}
        coerced: dict[str, object] = {}
        for name, value in parsed.items():
            if name not in allowed_fields or value is None:
                continue
            if name in _DATE_FIELDS:
                coerced[name] = _coerce_date(name, value)
            elif name in _NUMERIC_FIELDS:
                coerced[name] = _coerce_number(name, value)
            else:
                coerced[name] = value

        missing = [f"missing field {name}" for name in _REQUIRED_FIELDS[doc_type] if coerced.get(name) is None]
        if missing:
            raise IncompleteExtraction(missing)

        return ExtractResult(doc_type=doc_type, **coerced)
