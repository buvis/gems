"""LLM-backed structured field extractor (Ollama /api/chat).

Sends OCR text plus the already-determined ``doc_type`` to a local Ollama
instance and parses the JSON response into an ``ExtractResult``. The
``requests`` import is deferred until ``extract`` runs so the module is
loadable without the optional ``[doc]`` extra installed.
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal
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

_PINNED_FIELD_ALIASES: dict[str, str] = {
    "doc_number": "number",
    "doc_date": "date",
    "doc_amount": "amount",
    "doc_currency": "currency",
}


class IncompleteExtraction(Exception):
    """Raised when the extractor cannot produce a complete, usable result.

    The ``transient`` flag distinguishes HTTP/transport failures (retryable)
    from semantic failures like missing fields or uncoercible values
    (not retryable - the model's output is fundamentally unusable for this
    document, retrying with the same input won't help).

    The ``partial`` field carries whatever fields the extractor was able to
    coerce before giving up. The pipeline surfaces these in triage proposals
    so a human reviewer sees what the model did find, not just a wall of
    nulls.
    """

    def __init__(
        self,
        reasons: list[str],
        *,
        transient: bool = False,
        partial: ExtractResult | None = None,
    ) -> None:
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
            partial: An ``ExtractResult`` populated with the fields the
                extractor successfully coerced before failing, or ``None``
                when no useful fields were obtained (e.g. JSON parse failure
                or HTTP transport error). The triage path surfaces these in
                the proposal even when extraction was "incomplete".
        """
        super().__init__("; ".join(reasons))
        self.reasons = reasons
        self.transient = transient
        self.partial = partial


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
    return _reduced_system_prompt(doc_type, omit_fields=set())


def _reduced_system_prompt(doc_type: str, *, omit_fields: set[str]) -> str:
    required = ", ".join(name for name in _REQUIRED_FIELDS[doc_type] if name not in omit_fields)
    return (
        "You extract structured fields from scanned business documents.\n"
        f"The document type is: {doc_type}.\n"
        f"Required fields: {required}.\n"
        "Return STRICT JSON keyed by these field names. Omit unknown fields or set them to null.\n"
        "\n"
        "Rules:\n"
        "- Dates: ISO 8601 (YYYY-MM-DD). Reorder digits from formats like 15.11.2024, "
        "15/11/2024, or 2024-11-15 to YYYY-MM-DD before returning.\n"
        "- Amounts and balances: numeric only, no currency symbols, no thousands separators. "
        "Convert European-style 1 234,56 or 1.234,56 to 1234.56.\n"
        "- Currency: ISO 4217 code (CZK, EUR, USD, ...). Map symbols where present "
        "(Kč → CZK, € → EUR, $ → USD).\n"
        "- The OCR text may contain noise: line breaks splitting numbers, hyphenation across "
        "lines, accented characters mis-recognised. Reconstruct the most plausible value.\n"
        "- For invoices, the issue date (e.g. 'datum vystavení', 'date of issue') goes into "
        "the 'date' field; the payment due date (e.g. 'datum splatnosti', 'due date') goes "
        "into 'payment_due_date'.\n"
        "- The user message may include a 'Hints' section with the original filename or email "
        "subject. When the OCR text is ambiguous, treat hints as supporting evidence; for "
        "invoices the original filename is often the invoice number itself.\n"
    )


def _user_prompt(ocr_text: str, hints: dict[str, str] | None = None) -> str:
    parts = [f"OCR text:\n{ocr_text}"]
    if hints:
        hint_lines = [f"- {key}: {value}" for key, value in hints.items() if value]
        if hint_lines:
            parts.append("Hints:\n" + "\n".join(hint_lines))
    return "\n\n".join(parts) + "\n"


def _normalize_pinned_fields(pinned: dict[str, object]) -> dict[str, object]:
    allowed_fields = set(ExtractResult.model_fields.keys()) - {"doc_type"}
    normalized: dict[str, object] = {}
    for key, value in pinned.items():
        field_name = _PINNED_FIELD_ALIASES.get(key, key)
        if field_name in allowed_fields:
            normalized[field_name] = value
    return normalized


def _coerce_date(name: str, value: object) -> datetime.date:
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if not isinstance(value, str) or not value:
        raise IncompleteExtraction([f"could not coerce date '{value}' for field {name}"])
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise IncompleteExtraction([f"could not coerce date '{value}' for field {name}: {exc}"]) from exc


def _coerce_number(name: str, value: object) -> float:
    # ``Decimal`` is accepted because the rule engine's
    # ``strip_whitespace_to_decimal`` transform returns one for pinned amounts;
    # ``float(Decimal(...))`` is well-defined.
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        raise IncompleteExtraction([f"could not coerce number '{value}' for field {name}"])
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise IncompleteExtraction([f"could not coerce number '{value}' for field {name}: {exc}"]) from exc


def _coerce_one_field(name: str, value: object) -> object:
    """Apply per-field coercion (dates / numerics / passthrough)."""
    if name in _DATE_FIELDS:
        return _coerce_date(name, value)
    if name in _NUMERIC_FIELDS:
        return _coerce_number(name, value)
    return value


def _coerce_parsed(parsed: dict[str, object]) -> tuple[dict[str, object], list[str], set[str]]:
    """Coerce every recognised field, accumulating errors instead of bailing.

    Returns a triple of:

    - ``coerced``: name → coerced value for fields that came through cleanly.
    - ``coerce_errors``: human-readable reasons for fields whose value couldn't
      be coerced (e.g. non-ISO date string, non-numeric amount).
    - ``errored_fields``: field names that contributed a ``coerce_errors``
      entry; the caller uses this to suppress redundant ``missing field …``
      reasons for the same field.

    Coercion errors are deliberately collected rather than raised so the
    caller can still build a partial ``ExtractResult`` from the fields that
    *did* coerce - the triage proposal then surfaces the model's correct
    fields alongside reasons for the bad ones.
    """
    allowed_fields = set(ExtractResult.model_fields.keys()) - {"doc_type"}
    coerced: dict[str, object] = {}
    coerce_errors: list[str] = []
    errored_fields: set[str] = set()
    for name, value in parsed.items():
        if name not in allowed_fields or value is None:
            continue
        try:
            coerced[name] = _coerce_one_field(name, value)
        except IncompleteExtraction as exc:
            coerce_errors.extend(exc.reasons)
            errored_fields.add(name)
    return coerced, coerce_errors, errored_fields


class Extractor:
    """Extract structured fields from OCR text via an Ollama /api/chat endpoint."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings

    def extract(
        self,
        ocr_text: str,
        doc_type: str,
        *,
        hints: dict[str, str] | None = None,
    ) -> ExtractResult:
        """Extract structured fields for ``doc_type`` from OCR text via Ollama.

        Thin shim that forwards to :meth:`extract_with_model` using the
        configured primary model. Kept for callers that don't need to
        substitute the model.

        Args:
            ocr_text: Page text from OCR / pdfminer.
            doc_type: One of the canonical types in ``DOC_TYPES``.
            hints: Optional supporting signals (original filename, email
                subject) appended to the user prompt as a 'Hints' block.
                The model treats them as evidence, not authoritative facts.

        Raises:
            ValueError: ``doc_type`` is not one of the canonical types.
            IncompleteExtraction: HTTP transport failed (``transient=True``),
                the response was not parseable JSON, the response was not a
                JSON object, a value could not be coerced (e.g. non-ISO date,
                non-numeric amount), or one or more required fields were
                missing (``transient=False`` for these semantic failures).
            requests.exceptions.Timeout: Re-raised unwrapped so callers can
                distinguish slow-LLM scenarios from other failures.
        """
        return self.extract_with_model(
            ocr_text,
            doc_type,
            model=self._settings.primary_model,
            hints=hints,
        )

    def extract_with_model(
        self,
        ocr_text: str,
        doc_type: str,
        *,
        model: str,
        hints: dict[str, str] | None = None,
    ) -> ExtractResult:
        """Like :meth:`extract` but the caller picks the Ollama model name.

        Used by the pipeline's retry helper to substitute ``fallback_model``
        for ``primary_model`` after exhausted retries.
        """
        if doc_type not in DOC_TYPES:
            raise ValueError(f"doc_type must be one of {DOC_TYPES}, got {doc_type!r}")

        # Lazy import keeps the module loadable without the [doc] extra installed.
        import requests

        url = f"{self._settings.endpoint.rstrip('/')}/api/chat"
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": _system_prompt(doc_type)},
                {"role": "user", "content": _user_prompt(ocr_text, hints)},
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

        coerced, coerce_errors, errored_fields = _coerce_parsed(parsed)

        # Skip the missing-field reason for fields that already failed
        # coercion - the coerce error names them more precisely.
        missing = [
            f"missing field {name}"
            for name in _REQUIRED_FIELDS[doc_type]
            if coerced.get(name) is None and name not in errored_fields
        ]

        if coerce_errors or missing:
            partial = ExtractResult(doc_type=doc_type, **coerced)
            raise IncompleteExtraction(coerce_errors + missing, partial=partial)

        return ExtractResult(doc_type=doc_type, **coerced)

    def extract_with_pinned(
        self,
        ocr_text: str,
        doc_type: str,
        pinned: dict[str, object],
        *,
        model: str,
        hints: dict[str, str] | None = None,
    ) -> ExtractResult:
        """Extract with some fields pre-pinned by the rule engine.

        Skips the LLM entirely if ``pinned`` covers all required fields for
        ``doc_type``. Otherwise asks the LLM only for un-pinned required fields
        and merges pinned values verbatim, with pinned values taking precedence.
        """
        if doc_type not in DOC_TYPES:
            raise ValueError(f"doc_type must be one of {DOC_TYPES}, got {doc_type!r}")

        normalized = _normalize_pinned_fields(pinned)
        normalized_coerced = {name: _coerce_one_field(name, value) for name, value in normalized.items()}
        required = set(_REQUIRED_FIELDS[doc_type]) - set(normalized_coerced.keys())
        if not required:
            return ExtractResult(doc_type=doc_type, **normalized_coerced)

        # Lazy import keeps the module loadable without the [doc] extra installed.
        import requests

        url = f"{self._settings.endpoint.rstrip('/')}/api/chat"
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": _reduced_system_prompt(doc_type, omit_fields=set(normalized_coerced))},
                {"role": "user", "content": _user_prompt(ocr_text, hints)},
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

        parsed_unpinned = {name: value for name, value in parsed.items() if name not in normalized_coerced}
        coerced, coerce_errors, errored_fields = _coerce_parsed(parsed_unpinned)
        coerced.update(normalized_coerced)

        missing = [
            f"missing field {name}"
            for name in _REQUIRED_FIELDS[doc_type]
            if coerced.get(name) is None and name not in errored_fields
        ]

        if coerce_errors or missing:
            partial = ExtractResult(doc_type=doc_type, **coerced)
            raise IncompleteExtraction(coerce_errors + missing, partial=partial)

        return ExtractResult(doc_type=doc_type, **coerced)
