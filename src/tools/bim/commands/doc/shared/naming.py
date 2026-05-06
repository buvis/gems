from __future__ import annotations

import re
import unicodedata

__all__ = [
    "CANONICAL_REGEX",
    "DOC_TYPES",
    "SLUG_REGEX",
    "build_canonical_filename",
    "slugify",
]

DOC_TYPES: tuple[str, ...] = (
    "invoice",
    "receipt",
    "statement",
    "contract",
    "certificate",
    "reminder",
    "correspondence",
    "other",
)

_DOC_TYPE_ALT = "|".join(DOC_TYPES)
CANONICAL_REGEX = re.compile(
    r"^(?P<zk>\d{14})-"
    r"(?P<issuer>[a-z0-9]+(?:-[a-z0-9]+)*)-"
    r"(?P<title>[a-z0-9]+(?:-[a-z0-9]+)*)\."
    rf"(?P<doc_type>{_DOC_TYPE_ALT})\."
    r"(?P<ext>[a-z0-9]+)$"
)

_ZK_REGEX = re.compile(r"^\d{14}$")
SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Normalize text to a kebab-case ASCII slug.

    NFKD normalize -> unidecode transliterate -> lowercase ->
    collapse non-[a-z0-9] runs to single hyphen -> strip outer hyphens.
    Raises ValueError if the resulting slug is empty.
    """
    # Lazy import keeps the module loadable without the [doc] extra installed.
    from unidecode import unidecode

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = unidecode(normalized).lower()
    hyphenated = _NON_ALNUM.sub("-", ascii_text)
    stripped = hyphenated.strip("-")
    if not stripped:
        raise ValueError(f"slugify produced empty result from input: {text!r}")
    return stripped


def build_canonical_filename(
    *,
    zk_timestamp: str,
    issuer_slug: str,
    title_or_number: str,
    doc_type: str,
    ext: str = "pdf",
) -> str:
    """Compose a canonical filename per the spec grammar."""
    if not _ZK_REGEX.match(zk_timestamp):
        raise ValueError(f"zk_timestamp must be 14 digits, got {zk_timestamp!r}")
    if not SLUG_REGEX.match(issuer_slug):
        raise ValueError(f"issuer_slug must be lowercase kebab-case ASCII, got {issuer_slug!r}")
    if doc_type not in DOC_TYPES:
        raise ValueError(f"doc_type must be one of {DOC_TYPES}, got {doc_type!r}")
    if not SLUG_REGEX.match(ext):
        raise ValueError(f"ext must be lowercase alphanumeric, got {ext!r}")
    if not title_or_number or not title_or_number.strip():
        raise ValueError(f"title_or_number must be non-empty, got {title_or_number!r}")

    title_slug = slugify(title_or_number)
    result = f"{zk_timestamp}-{issuer_slug}-{title_slug}.{doc_type}.{ext}"
    if not CANONICAL_REGEX.match(result):
        raise ValueError(f"composed filename failed canonical regex: {result}")
    return result
