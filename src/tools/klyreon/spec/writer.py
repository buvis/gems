"""Serialize a :class:`Document` back to Markdown with YAML frontmatter.

Serialization is deterministic and canonical so a parse/serialize round-trip
over a canonically-formatted corpus is byte-stable:

- Known keys first, in spec order (:data:`KNOWN_KEY_ORDER`); unknown keys
  after, in their original relative order (spec 14).
- Block style throughout (no flow ``[...]``/``{...}``), two-space indentation,
  list items indented under their key.
- Scalars quoted only when YAML would otherwise misparse them (embedded colon,
  leading indicator, a value that implicitly resolves to a non-string), using
  the same rule PyYAML's resolver applies, so ``id: "20260411145300"`` keeps
  its quotes and ``type: note`` does not.

Every write goes through :func:`buvis.pybase.filesystem.atomic_write_text`;
there is no bare ``Path.write_text`` anywhere in the tool (a grep test enforces
this).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from buvis.pybase.filesystem import atomic_write_text

from klyreon.spec.model import KNOWN_KEY_ORDER, Document
from klyreon.spec.parser import KlyreonSafeLoader

__all__ = ["serialize", "write_document"]

_KNOWN_KEYS = frozenset(KNOWN_KEY_ORDER)


class _KlyreonDumper(yaml.SafeDumper):
    """Block-style dumper matched to :class:`KlyreonSafeLoader`.

    Overrides below force indentation of list items under their key and keep
    all collections in block style, so the output is stable and diff-friendly.
    """


_RESOLVER = KlyreonSafeLoader(b"")


def _resolved_tag(data: str) -> str:
    """Return the YAML tag the loader would assign to the plain scalar ``data``."""
    tag = _RESOLVER.resolve(yaml.ScalarNode, data, (True, False))  # type: ignore[no-untyped-call]
    return str(tag)


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """Quote a string only when the loader would not read it back as that string.

    A bare scalar is safe when it round-trips through the resolver to the
    ``str`` tag. Anything the resolver would tag as int/float/bool/null/etc.
    (e.g. a 14-digit id, ``true``, ``2026-01-01``) is emitted double-quoted.
    """
    style = "" if _resolved_tag(data) == "tag:yaml.org,2002:str" else '"'
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_KlyreonDumper.add_representer(str, _represent_str)


def _ordered_frontmatter(doc: Document) -> dict[str, Any]:
    """Return the frontmatter re-ordered: known keys (spec order) then unknown."""
    ordered: dict[str, Any] = {}
    for key in KNOWN_KEY_ORDER:
        if key in doc.frontmatter:
            ordered[key] = doc.frontmatter[key]
    for key, value in doc.frontmatter.items():
        if key not in _KNOWN_KEYS:
            ordered[key] = value
    return ordered


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.dump(
        data,
        Dumper=_KlyreonDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=1_000_000,
        indent=2,
    )


def serialize(doc: Document) -> str:
    """Serialize ``doc`` to the full file text (frontmatter fence + body)."""
    front = _dump_yaml(_ordered_frontmatter(doc)) if doc.frontmatter else ""
    # yaml.dump always ends with a newline; strip it so the fence is clean.
    front = front.rstrip("\n")
    parts = ["---\n", front, "\n---\n", doc.body]
    return "".join(parts)


def write_document(doc: Document, path: Path) -> None:
    """Serialize ``doc`` and write it to ``path`` atomically."""
    atomic_write_text(path, serialize(doc))
