"""``klyreon new`` -- write one spec-valid zettel with a unique ID."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from buvis.pybase.result import CommandResult

from klyreon.spec.enums import CLAIM_BEARING_CONCEPT_TYPES, Assent, Lifecycle
from klyreon.spec.model import Document, FileKind
from klyreon.spec.validator import validate_file
from klyreon.spec.writer import write_document
from klyreon.vault.ids import allocate_id


class CommandNew:
    """Create one zettel under ``<root>/wiki/notes`` with a collision-free id.

    Concept zettels (``concept_type`` set) get ``assent: tentative``,
    ``lifecycle: fleeting``, ``processed: false``; utility zettels get none of
    those. The H1 equals the title. The written file validates.
    """

    def __init__(
        self,
        root: Path,
        *,
        zettel_type: str = "note",
        title: str,
        concept_type: str | None = None,
        now: dt.datetime | None = None,
    ) -> None:
        self.root = root
        self.zettel_type = zettel_type
        self.title = title
        self.concept_type = concept_type
        self.now = now

    def execute(self) -> CommandResult:
        notes_dir = self.root / "wiki" / "notes"
        if not notes_dir.is_dir():
            return CommandResult(
                success=False,
                error=f"notes directory does not exist: {notes_dir}. Run 'klyreon init' first.",
            )

        moment = self.now or dt.datetime.now().astimezone()
        allocated = allocate_id(notes_dir, moment)

        frontmatter: dict[str, object] = {
            "id": allocated.id,
            "title": self.title,
            "created": allocated.created.isoformat(),
            "type": self.zettel_type,
        }
        if self.concept_type is not None:
            frontmatter["concept-type"] = self.concept_type
            frontmatter["assent"] = Assent.TENTATIVE.value
            frontmatter["lifecycle"] = Lifecycle.FLEETING.value
            frontmatter["processed"] = False
            if self.concept_type in CLAIM_BEARING_CONCEPT_TYPES:
                # Assertion-bearing shapes MUST carry >= 1 claim (spec 7.5); seed a
                # starter claim so the created zettel validates. The author replaces
                # the statement; the stable id c1 keeps later doubt references valid.
                frontmatter["claims"] = [{"id": "c1", "statement": self.title}]

        body = f"\n# {self.title}\n"
        doc = Document(
            path=f"wiki/notes/{allocated.filename}",
            kind=FileKind.ZETTEL,
            frontmatter=frontmatter,
            body=body,
            h1=self.title,
        )

        errors = validate_file(doc)
        if errors:
            detail = "; ".join(f"[{e.rule}] {e.message}" for e in errors)
            return CommandResult(success=False, error=f"refusing to write an invalid zettel: {detail}")

        target = notes_dir / allocated.filename
        write_document(doc, target)
        return CommandResult(
            success=True,
            output=str(target),
            metadata={"id": allocated.id, "path": doc.path},
        )
