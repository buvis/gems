from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IngestParams(BaseModel):
    """Parameters for the bim doc ingest command.

    Captures everything the pipeline needs from a CLI invocation, an
    issuer-inbox sweep, or a backfill walk. Source-specific fields are
    optional and only populated when relevant.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal[
        "email",
        "scan",
        "download",
        "issuer-inbox",
        "backfill-canonical",
        "backfill-noncanonical",
    ] = Field(..., description="Where the document entered the system")
    staging_path: Path = Field(..., description="Absolute path to the input PDF")
    original_filename: str | None = Field(None, description="Original filename if known")
    email_msgid: str | None = Field(None, description="IMAP message ID for email source")
    email_from: str | None = Field(None, description="Sender address for email source")
    email_subject: str | None = Field(None, description="Subject line for email source")
    issuer_slug_hint: str | None = Field(
        None,
        description="Pre-set issuer slug (when source is issuer-inbox or backfill)",
    )
    dry_run: bool = Field(False, description="Plan only, do not move or write files")
