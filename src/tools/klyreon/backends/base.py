"""The backend contract: prompt in, schema-validated payload out.

The seam between klyreon's deterministic loop and the operator CLI that does
the semantic work. The backend is a pure text-in, JSON-out function with no
filesystem access to the vault (the PRD "Backend contract" feature). klyreon
owns the entire write set, so the payload is *data*, never files.

Three things live here and nothing else:

- :class:`IngestPayload` -- the pydantic schema the backend must return. Its
  JSON schema is fed to the operator CLI (``--json-schema``) so shape
  enforcement happens in the CLI; a response that still does not match is a
  :class:`BackendError` with ``reason="schema"``, never a salvage attempt.
- :class:`BackendError` -- the one failure type, carrying a closed ``reason``
  (``timeout`` / ``exit`` / ``parse`` / ``schema``).
- :class:`Backend` -- the protocol every adapter implements:
  ``run(prompt, timeout) -> IngestPayload``.

Enum values (``shape``, ``type``, ``concept-type``, doubt ``mode``) are
validated against :mod:`klyreon.spec.enums` so a payload can only name a shape
in ``{aporia, refine, supersede}`` and a doubt mode in the Pyrrhonian five.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from klyreon.spec.enums import ConceptType, DoubtMode, ZettelType

__all__ = [
    "Backend",
    "BackendError",
    "ConflictEntry",
    "ConflictShape",
    "CorroborationEntry",
    "DoubtEntry",
    "IngestPayload",
    "LinkTarget",
    "PayloadClaim",
    "PayloadDoubtTarget",
    "ZettelDraft",
]

_ZETTEL_TYPES = frozenset(t.value for t in ZettelType)
_CONCEPT_TYPES = frozenset(t.value for t in ConceptType)
_DOUBT_MODES = frozenset(m.value for m in DoubtMode)


class BackendReason(str, Enum):
    """Closed set of reasons a backend call can fail (PRD backend contract)."""

    TIMEOUT = "timeout"
    EXIT = "exit"
    PARSE = "parse"
    SCHEMA = "schema"


class BackendError(RuntimeError):
    """A backend call failed, with a closed ``reason`` and a human ``detail``.

    ``reason`` is one of :class:`BackendReason`; it is what the pipeline logs in
    the trail and what tests assert on. ``detail`` is the free-text diagnostic.
    """

    def __init__(self, reason: BackendReason | str, detail: str) -> None:
        self.reason = BackendReason(reason)
        self.detail = detail
        super().__init__(f"[{self.reason.value}] {detail}")


class ConflictShape(str, Enum):
    """The three resolution shapes a conflict may take (spec 8)."""

    APORIA = "aporia"
    REFINE = "refine"
    SUPERSEDE = "supersede"


class PayloadClaim(BaseModel):
    """One structured claim on a drafted zettel (spec 7.5)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)


class PayloadDoubtTarget(BaseModel):
    """A foreign claim a doubt is raised against (spec 7.6)."""

    model_config = ConfigDict(extra="forbid")

    to: str = Field(min_length=1)
    claim: str | None = None


class DoubtEntry(BaseModel):
    """A Pyrrhonian doubt on a drafted zettel (spec 7.6)."""

    model_config = ConfigDict(extra="forbid")

    mode: str
    claim: str | None = None
    rationale: str = Field(min_length=1)
    target: PayloadDoubtTarget | None = None

    @field_validator("mode")
    @classmethod
    def _mode_in_enum(cls, value: str) -> str:
        if value not in _DOUBT_MODES:
            msg = f"doubt mode {value!r} is not one of {sorted(_DOUBT_MODES)}"
            raise ValueError(msg)
        return value


class ZettelDraft(BaseModel):
    """One zettel the backend proposes, before klyreon renders it to a file.

    No ``id``, ``created``, ``sources`` or ``assent``: klyreon allocates the id,
    sets the archive-first ``sources``, and applies the defaults (spec 2.4). The
    backend supplies only the semantic content.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str = Field(min_length=1)
    type: str = ZettelType.NOTE.value
    concept_type: str | None = Field(default=None, alias="concept-type")
    claims: list[PayloadClaim] = Field(default_factory=list)
    doubts: list[DoubtEntry] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    mocs: list[str] = Field(default_factory=list)
    body: str = ""

    @field_validator("type")
    @classmethod
    def _type_in_enum(cls, value: str) -> str:
        if value not in _ZETTEL_TYPES:
            msg = f"zettel type {value!r} is not one of {sorted(_ZETTEL_TYPES)}"
            raise ValueError(msg)
        return value

    @field_validator("concept_type")
    @classmethod
    def _concept_type_in_enum(cls, value: str | None) -> str | None:
        if value is not None and value not in _CONCEPT_TYPES:
            msg = f"concept-type {value!r} is not one of {sorted(_CONCEPT_TYPES)}"
            raise ValueError(msg)
        return value


class LinkTarget(BaseModel):
    """A target zettel + claim a conflict or corroboration points at."""

    model_config = ConfigDict(extra="forbid")

    to: str = Field(min_length=1)
    claim: str | None = None


class ConflictEntry(BaseModel):
    """One detected conflict between a new claim and an existing one.

    ``new_zettel`` indexes into :attr:`IngestPayload.zettels`; ``new_claim`` is
    the local claim id on that draft; ``target`` names the existing zettel and
    claim; ``shape`` is one of the three resolution shapes.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    new_zettel: int = Field(ge=0, alias="new-zettel")
    new_claim: str | None = Field(default=None, alias="new-claim")
    target: LinkTarget
    shape: ConflictShape
    rationale: str = ""


class CorroborationEntry(BaseModel):
    """One agreement between a new zettel and an existing one (spec 7.5)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    new_zettel: int = Field(ge=0, alias="new-zettel")
    target: LinkTarget
    rationale: str = ""


class IngestPayload(BaseModel):
    """The whole backend response for one source: drafts, conflicts, agreements.

    This is the model fed to ``--json-schema`` and the model every adapter
    validates against. ``extra="forbid"`` means an unexpected key is a schema
    failure, not a silently-ignored field.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    zettels: list[ZettelDraft] = Field(default_factory=list)
    conflicts: list[ConflictEntry] = Field(default_factory=list)
    corroborations: list[CorroborationEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _indices_in_range(self) -> IngestPayload:
        """Every conflict/corroboration ``new_zettel`` must index a real draft."""
        count = len(self.zettels)
        for conflict in self.conflicts:
            if conflict.new_zettel >= count:
                msg = f"conflict new-zettel index {conflict.new_zettel} out of range (have {count} zettels)"
                raise ValueError(msg)
        for corro in self.corroborations:
            if corro.new_zettel >= count:
                msg = f"corroboration new-zettel index {corro.new_zettel} out of range (have {count} zettels)"
                raise ValueError(msg)
        return self

    @classmethod
    def json_schema_str(cls) -> str:
        """Return the JSON Schema as a compact string, for ``--json-schema``."""
        import json

        return json.dumps(cls.model_json_schema())


@runtime_checkable
class Backend(Protocol):
    """One narrow interface every operator adapter implements.

    ``run`` is a pure text-in, payload-out function: it gets a prompt and a
    wall-clock timeout and returns a validated :class:`IngestPayload`, or raises
    :class:`BackendError`. It is given no vault path and writes nothing.
    """

    name: str

    def run(self, prompt: str, timeout: int) -> IngestPayload:
        """Turn ``prompt`` into a validated payload, or raise ``BackendError``."""
        ...
