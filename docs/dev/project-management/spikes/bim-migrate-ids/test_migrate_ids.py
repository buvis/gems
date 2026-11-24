from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

# migrate_ids.py is a standalone spike script, not a package — load directly
_script = Path(__file__).with_name("migrate_ids.py")
_spec = importlib.util.spec_from_file_location("migrate_ids", _script)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["migrate_ids"] = _mod
_spec.loader.exec_module(_mod)

plan_migration = _mod.plan_migration
NoteChange = _mod.NoteChange
Skip = _mod.Skip
MigrationError = _mod.MigrationError


def _vault(tmp_path: Path) -> Path:
    (tmp_path / "vault" / "notes").mkdir(parents=True)
    return (tmp_path / "vault").resolve()


def _fm(*lines: str, body: str = "Body.\n") -> bytes:
    return ("---\n" + "\n".join(lines) + "\n---\n" + body).encode()


def _put(vault: Path, rel: str, data: bytes) -> Path:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(root: Path) -> dict[Path, bytes | None]:
    return {p: (p.read_bytes() if p.is_file() else None) for p in root.rglob("*")}


def _moves(plan) -> list[tuple[Path, Path, str]]:
    return [(c.path, c.new_path, c.new_id) for c in plan.changes]


def test_prague_dst_summer_offset(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    first = _put(vault, "notes/20240715100000.md", _fm("id: 20240715100000", "date: 2024-07-15 10:00:00"))
    second = _put(vault, "notes/20240802011500.md", _fm("id: 20240802011500", 'date: "2024-08-02 01:15:00" # typed'))
    before = _snapshot(vault)

    plan = plan_migration(vault)

    assert _snapshot(vault) == before
    assert plan.changes == (
        NoteChange(
            path=first,
            new_path=vault / "notes" / "20240715080000.md",
            old_id="20240715100000",
            new_id="20240715080000",
            old_date_line="date: 2024-07-15 10:00:00",
            new_date_line="date: 2024-07-15 10:00:00+02:00",
            date_changed=True,
        ),
        NoteChange(
            path=second,
            new_path=vault / "notes" / "20240801231500.md",
            old_id="20240802011500",
            new_id="20240801231500",
            old_date_line='date: "2024-08-02 01:15:00" # typed',
            new_date_line='date: "2024-08-02 01:15:00+02:00" # typed',
            date_changed=True,
        ),
    )
    assert (plan.skips, plan.already_utc, plan.local_digit_mismatch) == ((), (), ())
    assert (plan.vault, plan.naive_timezone) == (vault, "Europe/Prague")

    empty = tmp_path / "empty"
    (empty / "notes").mkdir(parents=True)
    empty_plan = plan_migration(empty)
    assert (empty_plan.changes, empty_plan.skips, empty_plan.reference_count) == ((), (), 0)
    assert dict(empty_plan.hashes) == {}

    (tmp_path / "real" / "notes").mkdir(parents=True)
    (tmp_path / "linked").mkdir()
    (tmp_path / "linked" / "notes").symlink_to(tmp_path / "real" / "notes", target_is_directory=True)
    (tmp_path / "filevault").mkdir()
    (tmp_path / "filevault" / "notes").write_bytes(b"")
    for bad in (tmp_path / "missing", tmp_path / "linked", tmp_path / "filevault"):
        with pytest.raises(MigrationError, match="notes"):
            plan_migration(bad)


def test_prague_dst_winter_offset(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    winter = _put(vault, "notes/20240115100000.md", _fm("id: 20240115100000", "date: 2024-01-15 10:00:00"))
    drift = _put(vault, "notes/20240116100000.md", _fm("id: 20240116100000", "date: 2024-01-16 11:30:00"))
    short = _put(vault, "notes/202401171000.md", _fm("id: 202401171000", "date: 2024-01-17 10:00:00"))

    plan = plan_migration(vault)

    assert _moves(plan) == [
        (winter, vault / "notes" / "20240115090000.md", "20240115090000"),
        (drift, vault / "notes" / "20240116103000.md", "20240116103000"),
        (short, vault / "notes" / "20240117090000.md", "20240117090000"),
    ]
    assert plan.changes[0].new_date_line == "date: 2024-01-15 10:00:00+01:00"
    assert plan.changes[1].new_date_line == "date: 2024-01-16 11:30:00+01:00"
    assert plan.local_digit_mismatch == (drift,)

    new_york = plan_migration(vault, "America/New_York")

    assert new_york.naive_timezone == "America/New_York"
    assert new_york.changes[0].new_id == "20240115150000"
    assert new_york.changes[0].new_date_line == "date: 2024-01-15 10:00:00-05:00"


def test_aware_date_keeps_offset(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    plus5 = _put(vault, "notes/20240301100000.md", _fm("id: 20240301100000", "date: 2024-03-01T10:00:00+05:00"))
    utc = _put(vault, "notes/20240302100000.md", _fm("id: 20240302100000", "date: 2024-03-02T10:00:00Z"))
    naive = _put(vault, "notes/20240303100000.md", _fm("id: 20240303100000", "date: 2024-03-03T10:00:00"))

    for zone in ("Europe/Prague", "Asia/Tokyo"):
        plan = plan_migration(vault, zone)
        aware = plan.changes[0]
        assert (aware.path, aware.new_path, aware.new_id) == (
            plus5,
            vault / "notes" / "20240301050000.md",
            "20240301050000",
        )
        assert aware.old_date_line == aware.new_date_line == "date: 2024-03-01T10:00:00+05:00"
        assert aware.date_changed is False
        assert plan.already_utc == (utc,)
        assert [c.path for c in plan.changes] == [plus5, naive]
        assert plan.changes[1].date_changed is True

    assert plan_migration(vault).changes[1].new_id == "20240303090000"
    assert plan_migration(vault, "Asia/Tokyo").changes[1].new_id == "20240303010000"


def test_ambiguous_dst_time_is_skipped(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    fold = _put(vault, "notes/20241027023000.md", _fm("id: 20241027023000", "date: 2024-10-27 02:30:00"))
    summer = _put(vault, "notes/20241027013000.md", _fm("id: 20241027013000", "date: 2024-10-27 01:30:00"))
    winter = _put(vault, "notes/20241027033000.md", _fm("id: 20241027033000", "date: 2024-10-27 03:30:00"))

    plan = plan_migration(vault)

    assert plan.skips == (Skip(fold, "ambiguous local time (DST fold)"),)
    assert _mod.REASON_AMBIGUOUS == "ambiguous local time (DST fold)"
    # 03:30 CET is 02:30 UTC, the id the skipped fold note keeps, so it takes suffix 60
    assert _moves(plan) == [
        (summer, vault / "notes" / "20241026233000.md", "20241026233000"),
        (winter, vault / "notes" / "20241027023060.md", "20241027023060"),
    ]


def test_nonexistent_dst_time_is_skipped(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    gap = _put(vault, "notes/20240331023000.md", _fm("id: 20240331023000", "date: 2024-03-31 02:30:00"))
    before = _put(vault, "notes/20240331011500.md", _fm("id: 20240331011500", "date: 2024-03-31 01:15:00"))
    after = _put(vault, "notes/20240331033000.md", _fm("id: 20240331033000", "date: 2024-03-31 03:30:00"))

    plan = plan_migration(vault)

    assert plan.skips == (Skip(gap, "nonexistent local time (DST gap)"),)
    assert _mod.REASON_NONEXISTENT == "nonexistent local time (DST gap)"
    assert _moves(plan) == [
        (before, vault / "notes" / "20240331001500.md", "20240331001500"),
        (after, vault / "notes" / "20240331013000.md", "20240331013000"),
    ]
    assert plan.changes[0].new_date_line == "date: 2024-03-31 01:15:00+01:00"
    assert plan.changes[1].new_date_line == "date: 2024-03-31 03:30:00+02:00"


def test_date_only_is_skipped(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    dashed = _put(vault, "notes/20240301100000.md", _fm("id: 20240301100000", "date: 2024-03-01"))
    compact = _put(vault, "notes/20240302100000.md", _fm("id: 20240302100000", "date: 20240302"))
    bad_month = _put(vault, "notes/20240303100000.md", _fm("id: 20240303100000", "date: 2024-13-03 10:00:00"))
    word = _put(vault, "notes/20240304100000.md", _fm("id: 20240304100000", "date: soon"))
    timed = _put(vault, "notes/20240305100000.md", _fm("id: 20240305100000", "date: 2024-03-05 10:00:00"))

    plan = plan_migration(vault)

    assert set(plan.skips) == {
        Skip(dashed, "date has no time"),
        Skip(compact, "date has no time"),
        Skip(bad_month, "date cannot be parsed"),
        Skip(word, "date cannot be parsed"),
    }
    assert (_mod.REASON_DATE_ONLY, _mod.REASON_UNPARSEABLE) == ("date has no time", "date cannot be parsed")
    assert _moves(plan) == [(timed, vault / "notes" / "20240305090000.md", "20240305090000")]


def test_note_without_date_uses_old_id(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    short = _put(vault, "notes/202401151000.md", _fm("id: 202401151000", "title: Short"))
    full = _put(vault, "notes/20240715100000.md", _fm("id: 20240715100000", "title: Full"))
    bad = _put(vault, "notes/20241345100000.md", _fm("id: 20241345100000", "title: Bad"))
    fold = _put(vault, "notes/202410270230.md", _fm("id: 202410270230", "title: Fold"))

    plan = plan_migration(vault)

    assert plan.changes == (
        NoteChange(
            path=short,
            new_path=vault / "notes" / "20240115090000.md",
            old_id="202401151000",
            new_id="20240115090000",
            old_date_line=None,
            new_date_line="date: 2024-01-15T10:00:00+01:00",
            date_changed=True,
        ),
        NoteChange(
            path=full,
            new_path=vault / "notes" / "20240715080000.md",
            old_id="20240715100000",
            new_id="20240715080000",
            old_date_line=None,
            new_date_line="date: 2024-07-15T10:00:00+02:00",
            date_changed=True,
        ),
    )
    assert set(plan.skips) == {
        Skip(bad, "old id is not a valid time"),
        Skip(fold, "ambiguous local time (DST fold)"),
    }
    assert _mod.REASON_BAD_ID_TIME == "old id is not a valid time"
    assert plan.local_digit_mismatch == ()


def test_document_zettel_is_not_migrated(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    date = "date: 2024-05-01 10:00:00"
    docs = [
        _put(vault, "notes/20240501100000.md", _fm("id: 20240501100000", "type: document", date)),
        _put(vault, "notes/20240502100000.md", _fm("id: 20240502100000", "type: document # scanned", date)),
        _put(vault, "notes/20240503100000.md", _fm("id: 20240503100000", 'type: "document"', date)),
    ]
    plural = _put(vault, "notes/20240504100000.md", _fm("id: 20240504100000", "type: documents", date))
    in_body = _put(
        vault,
        "notes/20240505100000.md",
        _fm("id: 20240505100000", "type: note", date, body="type: document\n"),
    )
    block = _put(vault, "notes/20240506100000.md", _fm("id: 20240506100000", "type: |", "  document", date))
    empty = _put(vault, "notes/20240507100000.md", _fm("id: 20240507100000", "type:", date))

    plan = plan_migration(vault)

    assert [c.path for c in plan.changes] == [plural, in_body]
    assert [c.new_id for c in plan.changes] == ["20240501080000", "20240501080060"]
    assert set(plan.skips) == {
        Skip(block, "type is a block scalar or empty"),
        Skip(empty, "type is a block scalar or empty"),
    }
    assert _mod.REASON_TYPE_UNKNOWN == "type is a block scalar or empty"
    assert plan.already_utc == ()
    assert set(plan.hashes.values()) == {_sha(p) for p in [*docs, plural, in_body, block, empty]}


def test_slug_named_note_keeps_file_name(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    slug = _put(vault, "notes/contact/jane-doe.md", _fm("id: 20240715100000", "date: 2024-07-15 10:00:00"))
    titled = _put(
        vault, "notes/20240716100000-meeting.md", _fm("id: 20240716100000", "date: 2024-07-16 10:00:00")
    )
    nested = _put(vault, "notes/projects/20240717100000.md", _fm("id: 20240717100000", "date: 2024-07-17 10:00:00"))
    # 12-digit id followed by a digit in the stem: the stem does not start with the id as a token
    longer = _put(vault, "notes/20240115100000.md", _fm("id: 202401151000", "date: 2024-01-15 10:00:00"))

    plan = plan_migration(vault)

    assert _moves(plan) == [
        (longer, longer, "20240115090000"),
        (slug, slug, "20240715080000"),
        (titled, vault / "notes" / "20240716080000-meeting.md", "20240716080000"),
        (nested, vault / "notes" / "projects" / "20240717080000.md", "20240717080000"),
    ]
    assert plan.changes[1].new_date_line == "date: 2024-07-15 10:00:00+02:00"
    assert plan.skips == ()


def test_file_without_id_is_not_a_note(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    note = _put(vault, "notes/20240715100000.md", _fm("id: 20240715100000", "date: 2024-07-15 10:00:00"))
    links = (
        "See [[20240715100000]] and [[notes/20240715100000|the note]].\n"
        "Code: `[[20240715100000]]`.\n"
        "Not links: [[120240715100000]] [[20240715100000-other]] 20240715100000\n"
    )
    daily = _put(vault, "notes/daily/2024-07-15.md", _fm("title: Daily", "date: 2024-07-15 09:00:00", body=links))
    loose = _put(vault, "notes/loose.md", b"id: 20240716100000\ndate: 2024-07-16 10:00:00\n")
    alias = vault / "notes" / "alias.md"
    alias.symlink_to(note)
    (vault / "notes" / "folder.md").mkdir()
    before = _snapshot(vault)

    plan = plan_migration(vault)

    assert _snapshot(vault) == before
    assert _moves(plan) == [(note, vault / "notes" / "20240715080000.md", "20240715080000")]
    assert plan.skips == (Skip(alias, "file is a symlink"),)
    assert _mod.REASON_SYMLINK == "file is a symlink"
    assert plan.already_utc == ()
    assert plan.reference_count == 2
    assert set(plan.hashes.values()) == {_sha(note), _sha(daily), _sha(loose)}


def test_same_new_id_gets_suffix_60(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    prague = _put(vault, "notes/20240715100000.md", _fm("id: 20240715100000", "date: 2024-07-15 10:00:00"))
    moscow = _put(vault, "notes/20240715110000.md", _fm("id: 20240715110000", "date: 2024-07-15T11:00:00+03:00"))
    dubai = _put(vault, "notes/20240715120000.md", _fm("id: 20240715120000", "date: 2024-07-15T12:00:00+04:00"))
    _put(vault, "notes/scan.md", _fm("id: 20240801080000", "type: document"))
    after_doc = _put(vault, "notes/20240801100000.md", _fm("id: 20240801100000", "date: 2024-08-01 10:00:00"))
    shared_a = _put(vault, "notes/a/20240901100000.md", _fm("id: 20240901100000", "date: 2024-09-01 10:00:00"))
    shared_b = _put(vault, "notes/b/20240901100000.md", _fm("id: 20240901100000", "date: 2024-09-01 10:00:00"))
    drawn = _put(vault, "notes/20240902100000.md", _fm("id: 20240902100000", "date: 2024-09-02 10:00:00"))
    svg = _put(vault, "notes/20240902100000.svg", b"<svg/>")

    plan = plan_migration(vault)

    notes = vault / "notes"
    assert _moves(plan) == [
        (prague, notes / "20240715080000.md", "20240715080000"),
        (moscow, notes / "20240715080060.md", "20240715080060"),
        (dubai, notes / "20240715080061.md", "20240715080061"),
        (after_doc, notes / "20240801080060.md", "20240801080060"),
        (drawn, notes / "20240902080000.md", "20240902080000"),
    ]
    assert set(plan.skips) == {
        Skip(shared_a, "old stem shared with another file"),
        Skip(shared_b, "old stem shared with another file"),
    }
    assert _mod.REASON_STEM_SHARED == "old stem shared with another file"
    assert plan.kept_attachments == (svg,)
