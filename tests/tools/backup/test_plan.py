from __future__ import annotations

import pytest

from backup.step_result import PlanEntry


class TestPlanEntry:
    @pytest.mark.parametrize(
        ("label", "source", "out", "status", "reason", "replaces"),
        [
            ("notes", "/vault/notes", "/backup/notes.tar.gz", "run", "", False),
            ("notes-old", "/vault/notes-old", "/backup/notes-old.tar.gz", "skip", "source missing", True),
            ("photos", "/media/photos", "/archive/photos.tgz", "fail", "invalid output", False),
        ],
        ids=["run", "skip", "fail"],
    )
    def test_plan_entry_preserves_six_fields_in_tuple_order(
        self,
        label: str,
        source: str,
        out: str,
        status: str,
        reason: str,
        replaces: bool,
    ) -> None:
        entry = PlanEntry(label, source, out, status, reason, replaces)

        assert isinstance(entry, tuple)
        assert entry._fields == ("label", "source", "out", "status", "reason", "replaces")
        assert tuple(entry) == (label, source, out, status, reason, replaces)
        assert entry.label == label
        assert entry.source == source
        assert entry.out == out
        assert entry.status == status
        assert entry.reason == reason
        assert entry.replaces is replaces

    def test_plan_entry_accepts_named_fields_in_any_keyword_order(self) -> None:
        entry = PlanEntry(
            replaces=True,
            reason="destination exists",
            status="run",
            out="/backup/documents.tar.gz",
            source="/vault/documents",
            label="documents",
        )

        assert tuple(entry) == (
            "documents",
            "/vault/documents",
            "/backup/documents.tar.gz",
            "run",
            "destination exists",
            True,
        )

    def test_plan_entry_rejects_field_mutation(self) -> None:
        entry = PlanEntry("notes", "/vault/notes", "/backup/notes.tar.gz", "run", "", False)

        with pytest.raises(AttributeError):
            setattr(entry, "label", "changed")

        assert entry.label == "notes"
