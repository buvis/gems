"""Parse a Markdown file with YAML frontmatter into a :class:`Document`.

The YAML loader reuses the APPROACH proven by
``pybase.zettel._ZettelSafeLoader`` -- a SafeLoader whose implicit int
resolver drops the YAML 1.1 sexagesimal alternative -- without coupling to
bim's zettel model. On top of that it forces the ``id`` field to a string so
``id: 20260411145300`` parses as ``"20260411145300"`` and never as an int.

Frontmatter is loaded preserving insertion order (PyYAML already builds dicts
in document order), which is what lets the writer re-emit unknown keys in
their original relative order (spec 14).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

from klyreon.spec.model import Document, FileKind

__all__ = [
    "FrontmatterError",
    "KlyreonSafeLoader",
    "load_frontmatter",
    "parse_file",
    "parse_text",
    "split_frontmatter",
]

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
_H1_RE = re.compile(r"^#[ \t]+(.+?)[ \t]*$", re.MULTILINE)


class FrontmatterError(ValueError):
    """Raised when a file cannot be parsed into frontmatter + body."""


class KlyreonSafeLoader(yaml.SafeLoader):
    """SafeLoader without the YAML 1.1 sexagesimal int resolver.

    PyYAML's int resolver covers binary, octal, decimal, hex AND sexagesimal
    (``^[1-9][0-9_]*(?::[0-5]?[0-9])+$``), so ``11:30`` parses as base-60 int
    690 and a 14-digit timestamp can be mis-tagged. We rebuild the implicit
    resolver table without the sexagesimal alternative.
    """


_INT_NO_SEXAGESIMAL = re.compile(
    r"^[-+]?0b[0-1_]+$"
    r"|^[-+]?0[0-7_]+$"
    r"|^[-+]?(?:0|[1-9][0-9_]*)$"
    r"|^[-+]?0x[0-9a-fA-F_]+$",
)

KlyreonSafeLoader.yaml_implicit_resolvers = {
    key: [(tag, _INT_NO_SEXAGESIMAL if tag == "tag:yaml.org,2002:int" else regexp) for tag, regexp in resolvers]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split ``text`` into (raw frontmatter YAML, body).

    Raises:
        FrontmatterError: when the file does not open with a ``---`` fence.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        msg = "file does not start with a YAML frontmatter block delimited by '---'"
        raise FrontmatterError(msg)
    return match.group(1), match.group(2)


def load_frontmatter(raw: str) -> dict[str, Any]:
    """Load the raw frontmatter YAML into an ordered mapping.

    ``id`` is coerced to a string so an unquoted 14-digit timestamp survives
    as text. Raises :class:`FrontmatterError` on malformed YAML or a non-mapping.
    """
    try:
        loaded = yaml.load(raw, Loader=KlyreonSafeLoader)  # noqa: S506 - custom SafeLoader subclass
    except yaml.YAMLError as exc:
        msg = f"invalid YAML frontmatter: {exc}"
        raise FrontmatterError(msg) from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        msg = f"frontmatter must be a mapping, got {type(loaded).__name__}"
        raise FrontmatterError(msg)

    data = cast("dict[str, Any]", loaded)
    _coerce_string_fields(data)
    return data


#: Frontmatter fields that must stay verbatim strings rather than be coerced
#: by YAML into ``int``/``datetime``. ``id`` is a 14-digit timestamp; the three
#: timestamp fields are ISO 8601 strings whose ``T`` separator and offset must
#: survive a round-trip (PyYAML would otherwise re-emit a ``datetime`` with a
#: space separator).
_STRING_FIELDS: tuple[str, ...] = ("id", "created", "updated", "reviewed")


def _coerce_string_fields(data: dict[str, Any]) -> None:
    for field_name in _STRING_FIELDS:
        value = data.get(field_name)
        if value is not None and not isinstance(value, str):
            data[field_name] = _scalar_to_text(value)


def _scalar_to_text(value: Any) -> str:
    """Render a YAML-decoded scalar back to its canonical ISO text.

    A ``datetime``/``date`` is rendered in ISO 8601 (``T`` separator); anything
    else falls back to ``str``.
    """
    import datetime as _dt

    if isinstance(value, _dt.datetime):
        return value.isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    return str(value)


def _extract_h1(body: str) -> str | None:
    match = _H1_RE.search(body)
    return match.group(1) if match is not None else None


def parse_text(text: str, path: str, kind: FileKind) -> Document:
    """Parse in-memory ``text`` as a document of ``kind`` located at ``path``."""
    raw, body = split_frontmatter(text)
    frontmatter = load_frontmatter(raw)
    return Document(
        path=path,
        kind=kind,
        frontmatter=frontmatter,
        body=body,
        h1=_extract_h1(body),
    )


def parse_file(path: Path, kind: FileKind) -> Document:
    """Read and parse the file at ``path`` as a document of ``kind``."""
    text = path.read_text(encoding="utf-8")
    return parse_text(text, str(path), kind)
