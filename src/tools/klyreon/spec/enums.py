"""Closed vocabularies from the zettel format specification.

Each enum mirrors exactly one spec table and MUST stay in lockstep with it:

- :class:`SourceType`   -- spec 6.1 (source-document types)
- :class:`ZettelType`   -- spec 6.2 (zettel types)
- :class:`ConceptType`  -- spec 7.1 (epistemic shape)
- :class:`Assent`       -- spec 7.2 (Stoic assent)
- :class:`Lifecycle`    -- spec 7.3 (commonplacing state)
- :class:`DoubtMode`    -- spec 7.6 (Pyrrhonian modes)
- :class:`Relation`     -- spec 8 (relations vocabulary)
- :class:`AuxKind`      -- spec 3.3 (auxiliary file kinds)

The values are plain strings so a parsed frontmatter string compares directly
against the enum ``.value`` without coercion.
"""

from __future__ import annotations

from enum import Enum


class SourceType(str, Enum):
    """Source-document types (spec 6.1), used in ``sources/``."""

    ARTICLE = "article"
    BOOK = "book"
    QUOTE = "quote"
    TRANSCRIPT = "transcript"


class ZettelType(str, Enum):
    """Zettel types (spec 6.2), used in ``wiki/notes/``."""

    NOTE = "note"
    DEFINITION = "definition"
    PROCEDURE = "procedure"
    WIKI_ARTICLE = "wiki-article"
    CHEATSHEET = "cheatsheet"
    SNIPPET = "snippet"
    COURSE = "course"
    AI_PROMPT = "ai-prompt"


class ConceptType(str, Enum):
    """The epistemic shape of a concept zettel (spec 7.1)."""

    THESIS = "thesis"
    ARGUMENT = "argument"
    APORIA = "aporia"
    QUESTION = "question"
    EXAMPLE = "example"
    OBSERVATION = "observation"


class Assent(str, Enum):
    """The Stoic epistemic state (spec 7.2)."""

    ACCEPTED = "accepted"
    TENTATIVE = "tentative"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class Lifecycle(str, Enum):
    """The commonplacing distillation state (spec 7.3)."""

    FLEETING = "fleeting"
    LITERATURE = "literature"
    EVERGREEN = "evergreen"


class DoubtMode(str, Enum):
    """The five Pyrrhonian modes of doubt (spec 7.6)."""

    DISAGREEMENT = "disagreement"
    REGRESS = "regress"
    CONTEXT_RELATIVE = "context-relative"
    ASSUMPTION = "assumption"
    CIRCULAR = "circular"


class Relation(str, Enum):
    """The closed relations vocabulary (spec 8), capped at ten entries."""

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


class AuxKind(str, Enum):
    """Auxiliary-file kinds (spec 3.3)."""

    MOC = "moc"
    TRAIL = "trail"


#: Relations whose transitive closure must not contain a cycle (spec 8).
TRANSITIVE_RELATIONS: frozenset[str] = frozenset(
    {
        Relation.REQUIRES.value,
        Relation.BROADER_THAN.value,
        Relation.NARROWER_THAN.value,
    },
)

#: Concept-types that MUST carry at least one claim (spec 7.5).
CLAIM_BEARING_CONCEPT_TYPES: frozenset[str] = frozenset(
    {
        ConceptType.THESIS.value,
        ConceptType.ARGUMENT.value,
        ConceptType.OBSERVATION.value,
    },
)
