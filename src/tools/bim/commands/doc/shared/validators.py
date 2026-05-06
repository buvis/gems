"""Shared validators for doc subsystem field validation.

Centralises Pydantic field-validator regexes that were previously duplicated
across ``state_db.py``, ``triage.py``, and ``zettel_writer.py``.
"""

from __future__ import annotations

import re

__all__ = ["SHA256_HEX64_REGEX", "validate_sha256_hex64"]

SHA256_HEX64_REGEX = re.compile(r"^[0-9a-f]{64}$")


def validate_sha256_hex64(field_label: str, value: str) -> str:
    """Return ``value`` if it matches 64 lowercase hex chars; raise ``ValueError`` otherwise.

    Used by Pydantic ``field_validator`` callbacks. ``field_label`` is the
    name of the field surfaced in the error message (e.g. ``"sha256"``,
    ``"file_sha256"``), so the caller doesn't have to template the message
    itself.
    """
    if not SHA256_HEX64_REGEX.match(value):
        raise ValueError(f"{field_label} must be 64 lowercase hex chars, got {value!r}")
    return value
