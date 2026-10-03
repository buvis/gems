"""The derived graph every maintenance rule reads, built once per sweep.

Pure: one pass over ``wiki/notes/`` and the aux files, no console, no git, no
writes. :class:`VaultGraph` carries only concept zettels (``wiki/notes``) as
subjects — the rules act on zettels — but it resolves references against the
whole vault so a link to a source document still counts a source.

The three views the PRD names:

- :meth:`inbound` — every zettel that points a ``links.to`` at this path, with
  the relation, so a rule can ask "does anything ``supports`` me?".
- :meth:`corroborating_sources` — the distinct source documents backing a
  zettel, counted across its own ``sources`` plus the ``sources`` of every
  zettel that ``supports`` it (spec: corroboration is transitive through
  ``supports``). A zettel's own sources are excluded by the assent rule, not
  here; this view reports both and the caller decides.
- :meth:`open_disagreements` — whether any ``disagreement`` doubt sits on the
  zettel or, anywhere in the vault, names it as a ``target``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from klyreon.spec.enums import DoubtMode, Relation
from klyreon.spec.model import Document, FileKind
from klyreon.spec.parser import FrontmatterError, parse_file

__all__ = ["InboundLink", "VaultGraph"]


@dataclass(frozen=True, slots=True)
class InboundLink:
    """One link pointing AT a zettel: who points, and with which relation."""

    source: str
    rel: str


@dataclass(slots=True)
class VaultGraph:
    """Derived read-only views over one vault, built once by :meth:`build`.

    Attributes:
        zettels: Concept/utility zettels keyed by vault-relative path.
        mocs: Aux MOC documents keyed by vault-relative path.
    """

    zettels: dict[str, Document] = field(default_factory=dict)
    mocs: dict[str, Document] = field(default_factory=dict)
    _inbound: dict[str, list[InboundLink]] = field(default_factory=lambda: defaultdict(list))
    _own_sources: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    _supporters: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    _disagreement_targets: set[str] = field(default_factory=set)
    _self_disagreement: set[str] = field(default_factory=set)

    @classmethod
    def build(cls, root: Path) -> VaultGraph:
        """Build the graph with one pass over ``wiki/notes`` and ``wiki/mocs``."""
        graph = cls()
        graph._load_zettels(root)
        graph._load_mocs(root)
        graph._index()
        return graph

    def _load_zettels(self, root: Path) -> None:
        notes_dir = root / "wiki" / "notes"
        if not notes_dir.is_dir():
            return
        for md in sorted(notes_dir.rglob("*.md")):
            rel = md.relative_to(root).as_posix()
            try:
                doc = parse_file(md, FileKind.ZETTEL)
            except (FrontmatterError, OSError):
                continue
            self.zettels[rel] = Document(
                path=rel,
                kind=FileKind.ZETTEL,
                frontmatter=doc.frontmatter,
                body=doc.body,
                h1=doc.h1,
            )

    def _load_mocs(self, root: Path) -> None:
        mocs_dir = root / "wiki" / "mocs"
        if not mocs_dir.is_dir():
            return
        for md in sorted(mocs_dir.rglob("*.md")):
            rel = md.relative_to(root).as_posix()
            try:
                doc = parse_file(md, FileKind.AUX)
            except (FrontmatterError, OSError):
                continue
            self.mocs[rel] = Document(
                path=rel,
                kind=FileKind.AUX,
                frontmatter=doc.frontmatter,
                body=doc.body,
                h1=doc.h1,
            )

    def _index(self) -> None:
        for rel, doc in self.zettels.items():
            for source in doc.get("sources") or []:
                if isinstance(source, str):
                    self._own_sources[rel].add(source)

            for link in doc.get("links") or []:
                if not isinstance(link, dict):
                    continue
                target = link.get("to")
                relation = link.get("rel")
                if not isinstance(target, str) or not isinstance(relation, str):
                    continue
                self._inbound[target].append(InboundLink(source=rel, rel=relation))
                if relation == Relation.SUPPORTS.value:
                    self._supporters[target].append(rel)

            for doubt in doc.get("doubts") or []:
                if not isinstance(doubt, dict) or doubt.get("mode") != DoubtMode.DISAGREEMENT.value:
                    continue
                self._self_disagreement.add(rel)
                target = doubt.get("target")
                if isinstance(target, dict) and isinstance(target.get("to"), str):
                    self._disagreement_targets.add(target["to"])

    # ----------------------------------------------------------------- views

    def inbound(self, path: str) -> list[InboundLink]:
        """Return every link pointing AT ``path`` (empty when none)."""
        return list(self._inbound.get(path, []))

    def outbound_count(self, path: str) -> int:
        """Return the number of outbound ``links`` on the zettel at ``path``."""
        doc = self.zettels.get(path)
        if doc is None:
            return 0
        return len([link for link in (doc.get("links") or []) if isinstance(link, dict) and link.get("to")])

    def own_sources(self, path: str) -> set[str]:
        """Return the zettel's own ``sources`` set."""
        return set(self._own_sources.get(path, set()))

    def supporters(self, path: str) -> list[str]:
        """Return the zettels that ``supports`` ``path``."""
        return list(self._supporters.get(path, []))

    def corroborating_sources(self, path: str, *, include_own: bool = True) -> set[str]:
        """Return the distinct source documents backing ``path``.

        Counted across the zettel's own ``sources`` (when ``include_own``) plus
        the ``sources`` of every zettel that ``supports`` it. The assent rule
        passes ``include_own=False`` because corroboration must come from OTHER
        material; the lifecycle rule passes the default.
        """
        sources: set[str] = set(self._own_sources.get(path, set())) if include_own else set()
        for supporter in self._supporters.get(path, []):
            sources |= self._own_sources.get(supporter, set())
        return sources

    def open_disagreements(self, path: str) -> bool:
        """Return ``True`` when a ``disagreement`` doubt sits on or targets ``path``."""
        return path in self._self_disagreement or path in self._disagreement_targets
