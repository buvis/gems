from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class CreateNoteParams(BaseModel):
    """Parameters for the create-note command.

    Does not extend PathParams — creates a new zettel rather than operating
    on existing paths.
    """

    zettel_type: str | None = Field(None, description="Template type (note, project)")
    title: str | None = Field(None, description="Zettel title")
    tags: str | None = Field(None, description="Comma-separated tags")
    extra_answers: dict[str, str] | None = Field(None, description="Template question answers as key=value pairs")
    body: str | None = Field(None, description="Body content to append")
    source: Path | None = Field(None, description="Markdown source inside the vault inbox")
    dry_run: bool = Field(False, description="Preview the note without saving")
