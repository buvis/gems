from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

__all__ = [
    "CANONICAL_REGEX",
    "DOC_TYPES",
    "SLUG_REGEX",
    "build_canonical_filename",
    "resolve_collision",
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


def resolve_collision(
    *,
    zk_timestamp: str,
    issuer_slug: str,
    title_or_number: str,
    doc_type: str,
    business_root: Path,
    vault_dir: Path,
) -> tuple[str, str, Path]:
    """Increment the zk_timestamp seconds field until both target_pdf and
    the future zettel basename are free.

    Spec §11 rows 10/11 mandate a pre-write/pre-move collision check:
    increment the timestamp by one second and retry. The PDF and zettel
    basenames are linked (same canonical stem with .pdf / .md), so a
    single resolved zk_timestamp covers both.

    Caps at 60 attempts (one minute of collisions) and raises
    ``ValueError`` if exhausted - that condition signals a serious clock
    / state-db mismatch worth surfacing rather than silently overwriting.
    """
    candidate_zk = zk_timestamp
    for _ in range(60):
        canonical = build_canonical_filename(
            zk_timestamp=candidate_zk,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
        )
        target_pdf = business_root / issuer_slug / canonical
        zettel_basename = canonical.removesuffix(".pdf") + ".md"
        zettel_path = vault_dir / issuer_slug / zettel_basename
        if not target_pdf.exists() and not zettel_path.exists():
            target_pdf.parent.mkdir(parents=True, exist_ok=True)
            return canonical, candidate_zk, target_pdf
        candidate_zk = _increment_zk_seconds(candidate_zk)
    raise ValueError(f"could not resolve filename collision after 60 attempts starting from {zk_timestamp}")


def _increment_zk_seconds(zk_timestamp: str) -> str:
    """Add one second to a 14-digit zk timestamp with proper rollover."""
    dt = datetime.strptime(zk_timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return (dt + timedelta(seconds=1)).strftime("%Y%m%d%H%M%S")
