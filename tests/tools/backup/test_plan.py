from __future__ import annotations

import os
import tarfile
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from backup.capabilities import Capability
from backup.capabilities.tar_archive import TarArchive, _expand_stamp
from backup.config import BackupConfig
from backup.runner import Runner
from backup.step_result import PlanEntry

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("existing", [False, True])
def test_duplicate_outputs_rejected_before_writing(tmp_path: Path, dry_run: bool, existing: bool) -> None:
    out = tmp_path / "shared.tar.gz"
    if existing:
        out.write_bytes(b"preserve existing archive")
    instances = {}
    for name in ("notes", "notes-copy"):
        source = tmp_path / name
        source.mkdir()
        (source / "tiny.txt").write_bytes(name.encode())
        instances[name] = {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}}
    cfg = BackupConfig.model_validate({"instances": instances})

    results = list(Runner(cfg, dry_run=dry_run).run(list(cfg.instances.items())))

    assert len(results) == 2
    assert {result.label for result in results} == {"notes", "notes-copy"}
    for result in results:
        other = "notes-copy" if result.label == "notes" else "notes"
        assert result.success is False
        assert result.message == f"output '{out}' is also the output of '{other}'"
    assert out.exists() is existing
    if existing:
        assert out.read_bytes() == b"preserve existing archive"


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
        run_only = SimpleNamespace(inputs={}, run=lambda **kwargs: iter(()))
        plan_only = SimpleNamespace(inputs={}, plan=lambda **kwargs: PlanEntry("", "", "", "run", "", False))
        complete = SimpleNamespace(inputs={}, run=run_only.run, plan=plan_only.plan)

        assert isinstance(TarArchive(), Capability)
        assert isinstance(complete, Capability)
        assert not isinstance(run_only, Capability)
        assert not isinstance(plan_only, Capability)
        assert not isinstance(SimpleNamespace(), Capability)

    def test_capability_declares_accepted_inputs_and_defaults(self) -> None:
        assert TarArchive().inputs == {
            "source": "",
            "out": "",
            "engine": "python-tarfile",
            "items": None,
        }

    @pytest.mark.parametrize("existing", [False, True])
    def test_capability_plan_skips_independently_named_missing_source(self, tmp_path: Path, existing: bool) -> None:
        source = tmp_path / f"unavailable-{uuid4().hex}"
        out = tmp_path / "untouched.tar.gz"
        if existing:
            out.write_bytes(b"keep independent output")

        entry = TarArchive().plan(source=str(source), out=str(out), label="independent-source")

        assert entry == PlanEntry(
            "independent-source", str(source), str(out), "skip", f"source not found: {source}", existing
        )
        assert not source.exists()
        assert out.exists() is existing
        if existing:
            assert out.read_bytes() == b"keep independent output"

    @pytest.mark.parametrize("prefix", ["unregistered", "tar-engine"])
    def test_capability_plan_rejects_independently_named_unknown_engine(self, tmp_path: Path, prefix: str) -> None:
        source = tmp_path / "source"
        source.mkdir()
        out = tmp_path / "archive.tar.gz"
        engine = f"{prefix}-{uuid4().hex}"

        entry = TarArchive().plan(source=str(source), out=str(out), label="unknown-engine", engine=engine)

        assert entry == PlanEntry("unknown-engine", str(source), str(out), "fail", entry.reason, False)
        assert isinstance(entry.reason, str) and entry.reason
        assert not out.exists()

    @pytest.mark.parametrize("inside_source", [False, True])
    def test_capability_plan_resolves_output_parent_symlink_before_containment_check(
        self, tmp_path: Path, inside_source: bool
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        external = tmp_path / "external"
        external.mkdir()
        target = source if inside_source else external
        alias = tmp_path / "destination-alias"
        alias.symlink_to(target, target_is_directory=True)
        out = alias / "archive.tar.gz"

        entry = TarArchive().plan(source=str(source), out=str(out), label="symlink-output")

        assert entry.status == ("fail" if inside_source else "run")
        assert entry.label == "symlink-output"
        assert entry.source == str(source)
        assert entry.replaces is False
        if inside_source:
            assert isinstance(entry.reason, str) and entry.reason
        assert not out.exists()
        assert alias.is_symlink()

    @pytest.mark.parametrize(
        ("templates", "status"),
        [
            (["{name}"], "run"),
            (["{name}-copy"], "skip"),
            (["copy-{name}"], "skip"),
            (["nested/{name}"], "skip"),
            (["missing-first", "{name}"], "run"),
            (["{name}", "missing-last"], "run"),
        ],
    )
    def test_capability_plan_checks_independently_named_items_and_missing_lookalikes(
        self, tmp_path: Path, templates: list[str], status: str
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        name = f"record-{uuid4().hex}"
        (source / name).write_bytes(b"independent selected content")
        items = [template.format(name=name) for template in templates]
        out = tmp_path / "archive.tar.gz"

        entry = TarArchive().plan(source=str(source), out=str(out), label="independent-items", items=items)

        assert entry == PlanEntry("independent-items", str(source), str(out), status, entry.reason, False)
        if status == "skip":
            assert isinstance(entry.reason, str) and entry.reason
        assert (source / name).read_bytes() == b"independent selected content"
        assert not out.exists()

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
    def test_plan_does_not_walk_tree(
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

    @pytest.mark.parametrize("pattern", ["archive-%j.tar.gz", "archive-%a.tar.gz", "archive-%%Y.tar.gz"])
    @pytest.mark.parametrize("now", [datetime(2024, 2, 29, 6, 7, 8), datetime(2027, 12, 31, 21, 22, 23)])
    def test_stamp_expansion_preserves_strftime_directives_beyond_calendar_digits(
        self, pattern: str, now: datetime
    ) -> None:
        assert _expand_stamp(pattern, now) == now.strftime(pattern)

    @pytest.mark.parametrize(
        ("now", "label"),
        [
            (datetime(2026, 12, 31, 23, 59, 59), "vault-primary"),
            (datetime(2027, 1, 1, 0, 0, 1), "camera-secondary"),
        ],
    )
    def test_capability_plan_passes_now_to_output_stamp_expansion(
        self, tmp_path: Path, now: datetime, label: str
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        filename_pattern = "archive-%Y%m%d-%H%M%S.tar.gz"
        pattern = str(tmp_path / filename_pattern)
        out = tmp_path / now.strftime(filename_pattern)
        out.write_bytes(b"keep")

        entry = TarArchive().plan(source=str(source), out=pattern, label=label, now=now)

        assert entry == PlanEntry(label, str(source), str(out), "run", entry.reason, True)
        assert out.read_bytes() == b"keep"
        assert not (tmp_path / filename_pattern).exists()

    @pytest.mark.parametrize("dry_run", [False, True])
    @pytest.mark.parametrize("now", [datetime(2024, 2, 29, 6, 7, 8), datetime(2027, 12, 31, 21, 22, 23)])
    def test_capability_run_passes_now_to_archive_stamp_for_normal_and_dry_run(
        self, tmp_path: Path, now: datetime, dry_run: bool
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "tiny.txt").write_bytes(b"clock-selected content")
        filename_pattern = "archive-%Y%m%d-%H%M%S.tar.gz"
        pattern = str(tmp_path / filename_pattern)
        expected = tmp_path / now.strftime(filename_pattern)

        steps = list(
            TarArchive().run(source=str(source), out=pattern, label="unrelated-label", now=now, dry_run=dry_run)
        )

        assert len(steps) == 1
        assert steps[0].success is True
        assert steps[0].out_path == str(expected)
        assert expected.exists() is (not dry_run)
        assert not (tmp_path / filename_pattern).exists()
        if not dry_run:
            with tarfile.open(expected, "r:gz") as archive:
                member = archive.extractfile("source/tiny.txt")
                assert member is not None
                assert member.read() == b"clock-selected content"
