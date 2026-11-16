"""Tiromex note format: vocabularies, parsing, link and source readers, serialization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from .paths import to_vault_rel

if TYPE_CHECKING:
    from pathlib import Path

    from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

    from .paths import TiromexPaths


class ConceptType(str, Enum):
    """The epistemic shape of a concept note."""

    THESIS = "thesis"
    ARGUMENT = "argument"
    APORIA = "aporia"
    QUESTION = "question"
    EXAMPLE = "example"
    OBSERVATION = "observation"


class Assent(str, Enum):
    """The Stoic epistemic state."""

    ACCEPTED = "accepted"
    TENTATIVE = "tentative"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class Lifecycle(str, Enum):
    """The commonplacing distillation state."""

    FLEETING = "fleeting"
    LITERATURE = "literature"
    EVERGREEN = "evergreen"


class DoubtMode(str, Enum):
    """The five Pyrrhonian modes of doubt."""

    DISAGREEMENT = "disagreement"
    REGRESS = "regress"
    CONTEXT_RELATIVE = "context-relative"
    ASSUMPTION = "assumption"
    CIRCULAR = "circular"


class Relation(str, Enum):
    """The closed relations vocabulary."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXEMPLIFIES = "exemplifies"
    SUPERSEDES = "supersedes"
    DEFINES = "defines"
    ANALOGOUS_TO = "analogous-to"
    CAUSES = "causes"
    REQUIRES = "requires"
    BROADER_THAN = "broader-than"
    NARROWER_THAN = "narrower-than"


class NoteKind(str, Enum):
    """What a note in the tiromex folder is."""

    CONCEPT = "concept"
    INDEX = "index"
    RUN = "run"
    PLAIN = "plain"


CONCEPT_TYPE_VALUES = frozenset(m.value for m in ConceptType)
ASSENT_VALUES = frozenset(m.value for m in Assent)
LIFECYCLE_VALUES = frozenset(m.value for m in Lifecycle)
DOUBT_MODE_VALUES = frozenset(m.value for m in DoubtMode)
RELATION_VALUES = frozenset(m.value for m in Relation)

TRANSITIVE_RELATIONS = ("requires", "broader-than", "narrower-than")
CLAIM_BEARING_CONCEPT_TYPES = frozenset({"thesis", "argument", "observation"})
CONCEPT_NOTE_TYPES = (
    "note",
    "definition",
    "procedure",
    "wiki-article",
    "cheatsheet",
    "snippet",
    "course",
    "ai-prompt",
)
INDEX_TYPE = "index"
TX_RUN_TYPE = "tx-run"
FORBIDDEN_TAGS = frozenset({"person", "book"})
MEMBERS_OPEN = "<!-- tx:members -->"
MEMBERS_CLOSE = "<!-- /tx:members -->"
MIRROR_PREFIX = "mirror:"

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_SEPARATOR = re.compile(r"^---$", re.MULTILINE)
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
_MIRROR_SPLIT = re.compile(rf",\s*(?={MIRROR_PREFIX})")
_H1 = re.compile(r"^#[ \t]+(\S.*)$", re.MULTILINE)
_TITLE_DROP = str.maketrans("", "", '"\\[]|')


@dataclass(frozen=True, slots=True)
class WikiLink:
    """A wikilink: vault-relative target without ``.md`` and its title (``""`` when absent)."""

    target: str
    title: str


@dataclass(slots=True)
class TxNote:
    """A parsed note: vault-relative path, raw parse, kind and raw body text."""

    path: str
    data: ZettelData
    kind: NoteKind
    body: str


def parse_note(text: str, path: str) -> TxNote:
    """Parse note text without fixers and classify it.

    Args:
        text: The full note text.
        path: The vault-relative POSIX path of the note, with ``.md``.

    Returns:
        The parsed note. ``body`` runs from the end of the front matter up to the
        first line that is exactly ``---``, or to the end of the text.

    Raises:
        ValueError: When the text does not start with a front matter block, or
            the front matter or backmatter cannot be parsed.
    """
    from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.markdown import (
        MarkdownZettelFileParser,
    )

    front = _FRONT_MATTER.match(text)
    if front is None:
        raise ValueError(f"{path}: no front matter block at the start of the note")
    data = MarkdownZettelFileParser.parse(text)
    rest = text[front.end() :]
    separator = _SEPARATOR.search(rest)
    body = rest if separator is None else rest[: separator.start()]
    return TxNote(path=path, data=data, kind=classify(data), body=body)


def read_note(paths: TiromexPaths, file: Path) -> TxNote:
    """Read and parse a note file, recording its vault-relative path."""
    return parse_note(file.read_text(encoding="utf-8"), to_vault_rel(paths, file))


def classify(data: ZettelData) -> NoteKind:
    """Classify by the ``concept-type`` key, then by ``type``."""
    if "concept-type" in data.metadata:
        return NoteKind.CONCEPT
    note_type = data.metadata.get("type")
    if note_type == INDEX_TYPE:
        return NoteKind.INDEX
    if note_type == TX_RUN_TYPE:
        return NoteKind.RUN
    return NoteKind.PLAIN


def _strings(value: object) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [item for item in values if isinstance(item, str)]


def parse_links(value: object) -> list[WikiLink]:
    """Return every wikilink in a string or list of strings, never splitting on commas."""
    return [
        WikiLink(target=target, title=title) for item in _strings(value) for target, title in _WIKILINK.findall(item)
    ]


def format_links(links: list[WikiLink]) -> str:
    """Join links with ``", "``, removing ``"``, ``\\``, ``[``, ``]`` and ``|`` from titles."""
    return ", ".join(f"[[{link.target}|{link.title.translate(_TITLE_DROP)}]]" for link in links)


def relations(data: ZettelData) -> list[tuple[str, WikiLink]]:
    """Return one ``(relation, link)`` per link of each relation key, in ``Relation`` order."""
    return [(rel.value, link) for rel in Relation for link in parse_links(data.reference.get(rel.value))]


def parents(data: ZettelData) -> list[WikiLink]:
    """Return the links of the ``parent`` backmatter key."""
    return parse_links(data.reference.get("parent"))


def sources(data: ZettelData) -> list[str]:
    """Return the ``source`` values, split before every later ``mirror:``, stripped."""
    return [part.strip() for item in _strings(data.reference.get("source")) for part in _MIRROR_SPLIT.split(item)]


def link_file(target: str) -> str:
    """Return the vault-relative file of a link target."""
    return target + ".md"


def h1_titles(body: str) -> list[str]:
    """Return the stripped text of every line-start ``#`` heading in the body."""
    return [title.strip() for title in _H1.findall(body)]


def body_lines(body: str) -> list[str]:
    """Return the non-blank lines of the body."""
    return [line for line in body.splitlines() if line.strip()]


def as_datetime(value: object) -> datetime | None:
    """Read a datetime, date or ISO string as an aware datetime.

    A naive result gets the local timezone in force on its own date. Any other
    value, or an unreadable string, gives ``None``.
    """
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    return result if result.tzinfo is not None else result.astimezone()


def serialize(data: ZettelData) -> str:
    """Return the note text as ``bim format`` writes it."""
    from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
        MarkdownZettelFormatter,
    )

    return MarkdownZettelFormatter.format(data)
