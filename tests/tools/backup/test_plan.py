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
            ("notes", "/alternate/notes", "/alternate/notes.tar.gz", "skip", "source absent", True),
        ],
        ids=["run", "skip", "fail", "same-label-different-fields"],
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
        expected = (label, source, out, status, reason, replaces)

        assert isinstance(entry, tuple)
        assert entry._fields == ("label", "source", "out", "status", "reason", "replaces")
        assert tuple(entry) == expected
        assert entry.label == label
        assert entry.source == source
        assert entry.out == out
        assert entry.status == status
        assert entry.reason == reason
        assert entry.replaces is replaces
        assert entry[0] == label
        assert entry[1] == source
        assert entry[2] == out
        assert entry[3] == status
        assert entry[4] == reason
        assert entry[5] is replaces
        assert entry[:] == expected
        assert entry == expected
        assert entry == PlanEntry(label, source, out, status, reason, replaces)
        assert PlanEntry._make(iter(expected)) == expected

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
        assert entry._asdict() == {
            "label": "documents",
            "source": "/vault/documents",
            "out": "/backup/documents.tar.gz",
            "status": "run",
            "reason": "destination exists",
            "replaces": True,
        }

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("label", "changed"),
            ("source", "/different/source"),
            ("out", "/different/out.tar.gz"),
            ("status", "skip"),
            ("reason", "source missing"),
            ("replaces", True),
        ],
    )
    def test_plan_entry_rejects_field_mutation(self, field: str, value: str | bool) -> None:
        entry = PlanEntry("notes", "/vault/notes", "/backup/notes.tar.gz", "run", "", False)

        with pytest.raises(AttributeError):
            setattr(entry, field, value)

        assert tuple(entry) == ("notes", "/vault/notes", "/backup/notes.tar.gz", "run", "", False)

    def test_plan_entry_replace_returns_changed_record_and_preserves_original(self) -> None:
        entry = PlanEntry("notes", "/vault/notes", "/backup/notes.tar.gz", "run", "", False)

        changed = entry._replace(
            label="notes-old",
            source="/alternate/source",
            out="/alternate/out.tgz",
            status="fail",
            reason="output unavailable",
            replaces=True,
        )

        assert isinstance(changed, PlanEntry)
        assert changed == (
            "notes-old",
            "/alternate/source",
            "/alternate/out.tgz",
            "fail",
            "output unavailable",
            True,
        )
        assert tuple(entry) == ("notes", "/vault/notes", "/backup/notes.tar.gz", "run", "", False)

    @pytest.mark.parametrize(
        ("args", "kwargs"),
        [
            ((), {}),
            (("notes", "/vault/notes", "/backup/notes.tar.gz", "run", ""), {}),
            (("notes", "/vault/notes", "/backup/notes.tar.gz", "run", "", False, "extra"), {}),
            (("notes", "/vault/notes", "/backup/notes.tar.gz", "run", "", False), {"unknown": "extra"}),
        ],
        ids=["empty", "missing-field", "surplus-field", "unknown-keyword"],
    )
    def test_plan_entry_rejects_invalid_constructor_arguments(
        self,
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> None:
        with pytest.raises(TypeError):
            PlanEntry(*args, **kwargs)
