"""``bim tx new``: create one tiromex note through bim's create use case."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import CreateZettelUseCase
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

from bim.commands.tx.shared.format import (
    CLAIM_BEARING_CONCEPT_TYPES,
    CONCEPT_NOTE_TYPES,
    CONCEPT_TYPE_VALUES,
    Assent,
    Lifecycle,
    parse_note,
    serialize,
)
from bim.commands.tx.shared.paths import to_vault_rel
from bim.commands.tx.shared.validator import validate_note

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository

    from bim.commands.tx.shared.paths import TiromexPaths

_ZETTEL_TYPES = tuple(value for value in CONCEPT_NOTE_TYPES if value != "wiki-article")
_IGNORED_RULES = frozenset({"orphan-concept", "empty-body"})


class _TxTemplate:
    """Template for a new tiromex note: no questions, no hooks, H1-only body."""

    name = "tx"

    def __init__(self, folder: str, zettel_type: str, concept_type: str | None) -> None:
        self.folder = folder
        self.zettel_type = zettel_type
        self.concept_type = concept_type

    def questions(self) -> list[Any]:
        return []

    def hooks(self) -> list[Any]:
        return []

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        title = answers["title"]
        metadata: dict[str, Any] = {"type": self.zettel_type, "title": title}
        if self.concept_type is not None:
            metadata["concept-type"] = self.concept_type
            metadata["assent"] = Assent.TENTATIVE.value
            metadata["lifecycle"] = Lifecycle.FLEETING.value
            if self.concept_type in CLAIM_BEARING_CONCEPT_TYPES:
                metadata["claims"] = [{"id": "c1", "statement": title}]
        data = ZettelData()
        data.metadata = metadata
        data.sections = [(f"# {title}", "")]
        return data


class CommandTxNew:
    """Create one note in the tiromex folder; a concept type adds the concept fields."""

    def __init__(
        self,
        paths: TiromexPaths,
        repo: ZettelRepository,
        *,
        title: str,
        zettel_type: str = "note",
        concept_type: str | None = None,
    ) -> None:
        self.paths = paths
        self.repo = repo
        self.title = title
        self.zettel_type = zettel_type
        self.concept_type = concept_type

    def execute(self) -> CommandResult:
        """Validate the types, check the built note, then create it."""
        if self.zettel_type not in _ZETTEL_TYPES:
            return CommandResult(
                success=False, error=f"type {self.zettel_type!r} is not one of {', '.join(_ZETTEL_TYPES)}"
            )
        if self.concept_type is not None and self.concept_type not in CONCEPT_TYPE_VALUES:
            allowed = ", ".join(sorted(CONCEPT_TYPE_VALUES))
            return CommandResult(success=False, error=f"concept type {self.concept_type!r} is not one of {allowed}")
        folder = self.paths.folder.relative_to(self.paths.zettelkasten).as_posix()
        template = _TxTemplate(folder, self.zettel_type, self.concept_type)
        use_case = CreateZettelUseCase(self.paths.zettelkasten, self.repo)
        try:
            draft_path, zettel = use_case.prepare(template, {"title": self.title})
            note = parse_note(serialize(zettel.get_data()), to_vault_rel(self.paths, draft_path))
            found = [d for d in validate_note(note) if d.rule not in _IGNORED_RULES]
            if found:
                detail = "; ".join(f"[{d.rule}] {d.message}" for d in found)
                return CommandResult(success=False, error=f"refusing to write an invalid note: {detail}")
            path = use_case.execute(template, {"title": self.title})
        except (ValueError, OSError) as exc:
            return CommandResult(success=False, error=str(exc))
        return CommandResult(
            success=True,
            output=str(path),
            metadata={"id": path.stem, "path": to_vault_rel(self.paths, path)},
        )
