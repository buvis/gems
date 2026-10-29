from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from backup.capabilities import Capability
from backup.capabilities.tar_archive import TarArchive, _expand_stamp
from backup.step_result import PlanEntry

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


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


class TestCapabilityPlan:
    def test_capability_requires_plan_as_well_as_run(self) -> None:
        run_only = SimpleNamespace(run=lambda **kwargs: iter(()))
        plan_only = SimpleNamespace(plan=lambda **kwargs: PlanEntry("", "", "", "run", "", False))

        assert isinstance(TarArchive(), Capability)
        assert not isinstance(run_only, Capability)
        assert not isinstance(plan_only, Capability)
        assert not isinstance(SimpleNamespace(), Capability)

    @pytest.mark.parametrize(
        ("name", "label", "engine", "existing"),
        [
            ("notes", "daily-notes", "python-tarfile", False),
            ("photos", "camera-roll", "system-tar", True),
        ],
    )
    def test_capability_plan_returns_fields_and_replacement_for_valid_sources(
        self, tmp_path: Path, name: str, label: str, engine: str, existing: bool
    ) -> None:
        source = tmp_path / name
        source.mkdir()
        out = tmp_path / f"{name}-archive.tar.gz"
        if existing:
            out.write_bytes(b"existing archive")

        entry = TarArchive().plan(source=str(source), out=str(out), label=label, engine=engine)

        assert isinstance(entry, PlanEntry)
        assert entry == PlanEntry(label, str(source), str(out), "run", entry.reason, existing)
        assert isinstance(entry.reason, str)
        assert out.exists() is existing
        if existing:
            assert out.read_bytes() == b"existing archive"

    @pytest.mark.parametrize("name", ["absent", "absent-copy"])
    @pytest.mark.parametrize("existing", [False, True])
    def test_capability_plan_skips_missing_source_and_reports_existing_output(
        self, tmp_path: Path, name: str, existing: bool
    ) -> None:
        source = tmp_path / name
        out = tmp_path / f"{name}.tar.gz"
        if existing:
            out.write_bytes(b"keep")

        entry = TarArchive().plan(source=str(source), out=str(out), label=name)

        assert entry == PlanEntry(name, str(source), str(out), "skip", f"source not found: {source}", existing)
        assert not source.exists()
        assert out.exists() is existing
        if existing:
            assert out.read_bytes() == b"keep"

    @pytest.mark.parametrize("name", ["notes", "notes-copy"])
    @pytest.mark.parametrize("existing", [False, True])
    def test_capability_plan_fails_for_file_source_without_replacing_output(
        self, tmp_path: Path, name: str, existing: bool
    ) -> None:
        source = tmp_path / name
        source.write_bytes(b"not a directory")
        out = tmp_path / f"{name}.tar.gz"
        if existing:
            out.write_bytes(b"keep")

        entry = TarArchive().plan(source=str(source), out=str(out), label=name)

        assert entry == PlanEntry(name, str(source), str(out), "fail", entry.reason, existing)
        assert isinstance(entry.reason, str) and entry.reason
        assert source.read_bytes() == b"not a directory"
        assert out.exists() is existing
        if existing:
            assert out.read_bytes() == b"keep"

    @pytest.mark.parametrize(
        ("engine", "status"),
        [
            ("python-tarfile", "run"),
            ("system-tar", "run"),
            ("python-tarfile-extra", "fail"),
            ("extra-system-tar", "fail"),
            ("tar", "fail"),
            ("", "fail"),
        ],
    )
    def test_capability_plan_accepts_only_known_engine_names(self, tmp_path: Path, engine: str, status: str) -> None:
        source = tmp_path / "source"
        source.mkdir()
        out = tmp_path / "archive.tar.gz"

        entry = TarArchive().plan(source=str(source), out=str(out), engine=engine, label="engine")

        assert entry == PlanEntry("engine", str(source), str(out), status, entry.reason, False)
        assert isinstance(entry.reason, str)
        if status == "fail":
            assert entry.reason
        assert not out.exists()

    @pytest.mark.parametrize(
        ("relative_out", "status"),
        [
            ("notes/archive.tar.gz", "fail"),
            ("notes/nested/archive.tar.gz", "fail"),
            ("notes-copy/archive.tar.gz", "run"),
            ("other-notes/archive.tar.gz", "run"),
        ],
    )
    def test_capability_plan_confines_output_by_path_components(
        self, tmp_path: Path, relative_out: str, status: str
    ) -> None:
        source = tmp_path / "notes"
        source.mkdir()
        out = tmp_path / relative_out

        entry = TarArchive().plan(source=str(source), out=str(out), label="containment")

        assert entry == PlanEntry("containment", str(source), str(out), status, entry.reason, False)
        if status == "fail":
            assert isinstance(entry.reason, str) and entry.reason
        assert not out.exists()

    @pytest.mark.parametrize(
        ("items", "reason"),
        [
            ([], "items must not be empty"),
            ([""], "invalid item '': must be a relative path inside the source"),
            (["."], "invalid item '.': must be a relative path inside the source"),
            (["folder/.."], "invalid item 'folder/..': must be a relative path inside the source"),
            (["/notes"], "invalid item '/notes': must be a relative path inside the source"),
            (["../notes"], "invalid item '../notes': must be a relative path inside the source"),
            (["..notes"], "invalid item '..notes': must be a relative path inside the source"),
            (["present", "../notes"], "invalid item '../notes': must be a relative path inside the source"),
            (["../notes", "present"], "invalid item '../notes': must be a relative path inside the source"),
        ],
    )
    def test_capability_plan_rejects_invalid_items_even_beside_existing_items(
        self, tmp_path: Path, items: list[str], reason: str
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "present").write_bytes(b"selected")
        out = tmp_path / "archive.tar.gz"
        out.write_bytes(b"keep")

        entry = TarArchive().plan(source=str(source), out=str(out), items=items, label="items")

        assert entry == PlanEntry("items", str(source), str(out), "fail", reason, True)
        assert out.read_bytes() == b"keep"

    @pytest.mark.parametrize(
        ("items", "status"),
        [
            (["present"], "run"),
            (["nested/../present"], "run"),
            ([".present"], "run"),
            (["present-copy"], "skip"),
            (["copy-present"], "skip"),
            (["elsewhere/present"], "skip"),
            (["missing-first", "present"], "run"),
            (["present", "missing-last"], "run"),
            (["missing-first", "missing-last"], "skip"),
            (["present", "present", "folder", "folder/child"], "run"),
        ],
    )
    def test_capability_plan_uses_normalized_literal_items_and_all_selected_paths(
        self, tmp_path: Path, items: list[str], status: str
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "present").write_bytes(b"selected")
        (source / ".present").write_bytes(b"hidden")
        (source / "folder").mkdir()
        (source / "folder" / "child").write_bytes(b"child")
        out = tmp_path / "archive.tar.gz"

        entry = TarArchive().plan(source=str(source), out=str(out), items=items, label="selection")

        assert entry == PlanEntry("selection", str(source), str(out), status, entry.reason, False)
        assert isinstance(entry.reason, str)
        if status == "skip":
            assert entry.reason
        assert not out.exists()

    @pytest.mark.parametrize("name", ["link", "link-copy"])
    @pytest.mark.parametrize("target_exists", [False, True])
    def test_capability_plan_counts_final_symlinks_with_lexists(
        self, tmp_path: Path, name: str, target_exists: bool
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / f"{name}-target"
        if target_exists:
            target.write_bytes(b"target")
        (source / name).symlink_to(target)
        out = tmp_path / f"{name}.tar.gz"

        entry = TarArchive().plan(source=str(source), out=str(out), items=[name], label=name)

        assert entry == PlanEntry(name, str(source), str(out), "run", entry.reason, False)
        assert (source / name).is_symlink()
        assert not out.exists()

    @pytest.mark.parametrize("name", ["linked", "linked-copy"])
    def test_capability_plan_rejects_symlink_parent_components(self, tmp_path: Path, name: str) -> None:
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (target / "child").write_bytes(b"outside")
        (source / name).symlink_to(target, target_is_directory=True)
        out = tmp_path / f"{name}.tar.gz"
        item = f"{name}/child"

        entry = TarArchive().plan(source=str(source), out=str(out), items=[item], label=name)

        assert entry == PlanEntry(
            name,
            str(source),
            str(out),
            "fail",
            f"item '{item}' passes through symlink '{name}'",
            False,
        )
        assert (target / "child").read_bytes() == b"outside"
        assert not out.exists()

    @pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
    @pytest.mark.parametrize("items", [None, ["selected", "selected/child"]])
    def test_capability_plan_does_not_walk_read_write_or_invoke_archive_engines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str, items: list[str] | None
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "selected").mkdir()
        (source / "selected" / "child").write_bytes(b"keep source")
        out = tmp_path / "uncreated" / "archive.tar.gz"
        kwargs: dict[str, object] = dict(source=str(source), out=str(out), label="metadata", engine=engine)
        if items is not None:
            kwargs["items"] = items

        def forbidden(*args: object, **kwargs: object) -> None:
            pytest.fail("planning must use metadata only")

        with monkeypatch.context() as patch:
            patch.setattr(os, "walk", forbidden)
            patch.setattr(os, "scandir", forbidden)
            patch.setattr(os, "mkdir", forbidden)
            patch.setattr(os, "open", forbidden)
            patch.setattr("builtins.open", forbidden)
            patch.setattr("io.open", forbidden)
            patch.setattr("tarfile.open", forbidden)
            patch.setattr("subprocess.Popen", forbidden)
            entry = TarArchive().plan(**kwargs)

        assert entry == PlanEntry("metadata", str(source), str(out), "run", entry.reason, False)
        assert not out.parent.exists()
        assert (source / "selected" / "child").read_bytes() == b"keep source"


class TestStampExpansion:
    @pytest.mark.parametrize(
        ("pattern", "now", "expected"),
        [
            ("notes-%Y%m%d-%H%M%S.tar.gz", datetime(2026, 10, 30, 12, 34, 56), "notes-20261030-123456.tar.gz"),
            ("photos-%Y%m%d-%H%M%S.tgz", datetime(2027, 1, 2, 3, 4, 5), "photos-20270102-030405.tgz"),
            ("%Y/%m/%d-%Y.tar.gz", datetime(2024, 2, 29, 23, 59, 58), "2024/02/29-2024.tar.gz"),
            ("notes-Ymd-HMS.tar.gz", datetime(2026, 10, 30, 12, 34, 56), "notes-Ymd-HMS.tar.gz"),
            ("", datetime(2027, 1, 2, 3, 4, 5), ""),
        ],
    )
    def test_stamp_expansion_uses_passed_clock_and_preserves_literal_patterns(
        self, mocker: MockerFixture, pattern: str, now: datetime, expected: str
    ) -> None:
        clock = mocker.patch("backup.capabilities.tar_archive.datetime", autospec=True)
        clock.now.return_value = datetime(2001, 6, 7, 8, 9, 10)

        assert _expand_stamp(pattern, now) == expected

    @pytest.mark.parametrize("explicit_none", [False, True])
    @pytest.mark.parametrize("now", [datetime(2026, 12, 31, 23, 59, 59), datetime(2027, 1, 1, 0, 0, 1)])
    def test_stamp_expansion_falls_back_to_current_clock_when_now_is_absent(
        self, mocker: MockerFixture, explicit_none: bool, now: datetime
    ) -> None:
        clock = mocker.patch("backup.capabilities.tar_archive.datetime", autospec=True)
        clock.now.return_value = now
        pattern = "archive-%Y%m%d-%H%M%S.tar.gz"

        actual = _expand_stamp(pattern, None) if explicit_none else _expand_stamp(pattern)

        assert actual == now.strftime(pattern)

    @pytest.mark.parametrize(
        ("now", "filename"),
        [
            (datetime(2026, 12, 31, 23, 59, 59), "archive-20261231-235959.tar.gz"),
            (datetime(2027, 1, 1, 0, 0, 1), "archive-20270101-000001.tar.gz"),
        ],
    )
    def test_capability_plan_passes_now_to_output_stamp_expansion(
        self, tmp_path: Path, now: datetime, filename: str
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        pattern = str(tmp_path / "archive-%Y%m%d-%H%M%S.tar.gz")
        out = tmp_path / filename
        out.write_bytes(b"keep")

        entry = TarArchive().plan(source=str(source), out=pattern, label=filename, now=now)

        assert entry == PlanEntry(filename, str(source), str(out), "run", entry.reason, True)
        assert out.read_bytes() == b"keep"
        assert not (tmp_path / "archive-%Y%m%d-%H%M%S.tar.gz").exists()
