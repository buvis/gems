"""Issuer registry: load, resolve aliases, register new issuers.

The file lock uses ``fcntl.flock`` which is Unix-only. macOS and Linux are
supported targets; Windows is out of scope. Encrypted ``issuers.yml`` files
(e.g. via the dotfiles git-secret filter) are detected and rejected with an
actionable error - the file should look decrypted to all processes, which
means the smudge filter must be active.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bim.commands.doc.shared.atomic_write import atomic_write_text
from bim.commands.doc.shared.naming import SLUG_REGEX, slugify

__all__ = [
    "IssuerEntry",
    "IssuerRegistry",
    "load_registry",
    "register_issuer",
    "resolve_alias",
]


_PGP_MARKERS = (
    b"-----BEGIN PGP MESSAGE-----",
    b"-----BEGIN PGP ARMORED FILE-----",
    b"-----BEGIN ENCRYPTED MESSAGE-----",
)


class IssuerEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    display_name: str
    aliases: list[str] = []
    notes: str | None = None

    @field_validator("slug")
    @classmethod
    def _slug_is_canonical(cls, v: str) -> str:
        if not SLUG_REGEX.match(v):
            raise ValueError(f"slug {v!r} must be lowercase kebab-case ASCII (matching {SLUG_REGEX.pattern})")
        return v

    @field_validator("display_name")
    @classmethod
    def _display_name_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("display_name must be non-empty")
        return v

    @field_validator("aliases")
    @classmethod
    def _aliases_non_empty(cls, v: list[str]) -> list[str]:
        for alias in v:
            if not alias.strip():
                raise ValueError(f"aliases must contain only non-empty strings, got {v!r}")
        return v


class IssuerRegistry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    doc_types: list[str]
    reserved_slugs: list[str]
    issuers: dict[str, IssuerEntry]

    @model_validator(mode="after")
    def _verify_slug_keys_match(self) -> IssuerRegistry:
        for key, entry in self.issuers.items():
            if entry.slug != key:
                raise ValueError(f"Issuer slug {entry.slug!r} does not match dict key {key!r}")
        overlap = set(self.reserved_slugs) & set(self.issuers.keys())
        if overlap:
            raise ValueError(f"reserved_slugs and issuers keys must be disjoint, conflict: {sorted(overlap)}")
        return self


def _looks_like_ciphertext(raw: bytes) -> bool:
    head = raw[:200].lstrip()
    return any(head.startswith(marker) for marker in _PGP_MARKERS)


def _parse_registry(raw: bytes) -> IssuerRegistry:
    if _looks_like_ciphertext(raw):
        raise RuntimeError(
            "issuers.yml appears to be encrypted; is the dotfiles git filter "
            "active? Run `git config filter.git-secret.smudge` to verify."
        )
    parsed = yaml.safe_load(raw)
    if parsed is None:
        raise ValueError("issuers.yml is empty or YAML parse returned None")

    raw_issuers = parsed.get("issuers") or {}
    normalized_issuers: dict[str, dict[str, object]] = {}
    for slug, body in raw_issuers.items():
        merged = dict(body or {})
        merged["slug"] = slug
        normalized_issuers[slug] = merged

    return IssuerRegistry.model_validate(
        {
            "version": parsed.get("version"),
            "doc_types": parsed.get("doc_types") or [],
            "reserved_slugs": parsed.get("reserved_slugs") or [],
            "issuers": normalized_issuers,
        }
    )


def load_registry(path: Path) -> IssuerRegistry:
    """Load and validate an issuers.yml file."""
    raw = path.read_bytes()
    return _parse_registry(raw)


def _serialize(registry: IssuerRegistry) -> str:
    issuers_out: dict[str, dict[str, object]] = {}
    for slug, entry in registry.issuers.items():
        body: dict[str, object] = {"display_name": entry.display_name}
        if entry.aliases:
            body["aliases"] = list(entry.aliases)
        if entry.notes is not None:
            body["notes"] = entry.notes
        issuers_out[slug] = body

    payload = {
        "version": registry.version,
        "doc_types": list(registry.doc_types),
        "reserved_slugs": list(registry.reserved_slugs),
        "issuers": issuers_out,
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def register_issuer(
    registry_path: Path,
    lock_path: Path,
    *,
    slug: str,
    display_name: str,
    aliases: list[str] | None = None,
) -> IssuerRegistry:
    """Register a new issuer under exclusive flock, atomically rewriting the file.

    Raises ValueError if the slug is reserved, already present, or the display_name is empty.
    """
    if not display_name.strip():
        raise ValueError("display_name must be non-empty")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        current = load_registry(registry_path)

        if slug in current.reserved_slugs:
            raise ValueError(f"slug {slug!r} is reserved")
        if slug in current.issuers:
            raise ValueError(f"slug {slug!r} already registered")

        new_entry = IssuerEntry(
            slug=slug,
            display_name=display_name,
            aliases=list(aliases or []),
        )
        new_issuers = dict(current.issuers)
        new_issuers[slug] = new_entry

        new_registry = IssuerRegistry(
            version=current.version,
            doc_types=current.doc_types,
            reserved_slugs=current.reserved_slugs,
            issuers=new_issuers,
        )
        atomic_write_text(registry_path, _serialize(new_registry))
        return new_registry
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def resolve_alias(registry: IssuerRegistry, candidate: str) -> str | None:
    """Map an arbitrary issuer name (slug, alias, alias-with-diacritics,
    casing) to a canonical slug. Returns None if no match.
    """
    if candidate in registry.issuers:
        return candidate

    try:
        candidate_slug = slugify(candidate)
    except ValueError:
        return None

    if candidate_slug in registry.issuers:
        return candidate_slug

    for slug, entry in registry.issuers.items():
        for alias in entry.aliases:
            try:
                alias_slug = slugify(alias)
            except ValueError:
                continue
            if alias_slug == candidate_slug:
                return slug
    return None
