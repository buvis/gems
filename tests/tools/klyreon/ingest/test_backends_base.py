"""Phase 0: the backend contract (schema, errors, stub)."""

from __future__ import annotations

import pytest
from klyreon.backends.base import (
    BackendError,
    BackendReason,
    ConflictShape,
    IngestPayload,
)
from klyreon.backends.stub import StubBackend
from pydantic import ValidationError

pytestmark = pytest.mark.klyreon


class TestIngestPayloadSchema:
    def test_round_trip(self) -> None:
        payload = IngestPayload.model_validate(
            {
                "zettels": [
                    {
                        "title": "T",
                        "type": "note",
                        "concept-type": "thesis",
                        "claims": [{"id": "c1", "statement": "s"}],
                        "mocs": ["wiki/mocs/a.md"],
                        "body": "b",
                    },
                ],
                "conflicts": [
                    {
                        "new-zettel": 0,
                        "new-claim": "c1",
                        "target": {"to": "wiki/notes/20260101000000.md", "claim": "c1"},
                        "shape": "aporia",
                        "rationale": "r",
                    },
                ],
                "corroborations": [],
            },
        )
        # Dump by alias and re-validate -> identical object (round-trip).
        dumped = payload.model_dump(by_alias=True)
        again = IngestPayload.model_validate(dumped)
        assert again == payload
        assert again.conflicts[0].shape is ConflictShape.APORIA

    def test_shape_outside_three_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestPayload.model_validate(
                {
                    "zettels": [{"title": "T", "claims": [{"id": "c1", "statement": "s"}]}],
                    "conflicts": [
                        {
                            "new-zettel": 0,
                            "target": {"to": "wiki/notes/x.md", "claim": "c1"},
                            "shape": "coexist",  # not in {aporia, refine, supersede}
                        },
                    ],
                },
            )

    def test_doubt_mode_outside_five_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestPayload.model_validate(
                {
                    "zettels": [
                        {
                            "title": "T",
                            "doubts": [{"mode": "vibes", "claim": None, "rationale": "r"}],
                        },
                    ],
                },
            )

    def test_conflict_index_out_of_range_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestPayload.model_validate(
                {
                    "zettels": [],
                    "conflicts": [
                        {"new-zettel": 0, "target": {"to": "wiki/notes/x.md"}, "shape": "refine"},
                    ],
                },
            )

    def test_json_schema_str_is_valid_json(self) -> None:
        import json

        schema = json.loads(IngestPayload.json_schema_str())
        assert schema["type"] == "object"
        assert "zettels" in schema["properties"]


class TestStubBackend:
    def test_queue_returns_in_order(self) -> None:
        p1 = IngestPayload(zettels=[])
        p2 = IngestPayload(zettels=[])
        stub = StubBackend(payloads=[p1, p2])
        assert stub.run("x", 1) is p1
        assert stub.run("x", 1) is p2

    def test_exhausted_queue_raises_parse(self) -> None:
        stub = StubBackend(payloads=[])
        with pytest.raises(BackendError) as exc:
            stub.run("x", 1)
        assert exc.value.reason is BackendReason.PARSE

    def test_by_marker_match(self) -> None:
        p = IngestPayload(zettels=[])
        stub = StubBackend(by_marker={"MARK": p})
        assert stub.run("prompt with MARK inside", 1) is p

    def test_by_marker_no_match_raises_parse(self) -> None:
        stub = StubBackend(by_marker={"MARK": IngestPayload()})
        with pytest.raises(BackendError) as exc:
            stub.run("no marker here", 1)
        assert exc.value.reason is BackendReason.PARSE

    def test_stub_satisfies_protocol(self) -> None:
        from klyreon.backends.base import Backend

        assert isinstance(StubBackend(), Backend)
