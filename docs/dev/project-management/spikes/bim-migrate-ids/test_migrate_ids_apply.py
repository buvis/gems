from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

# migrate_ids.py is a standalone spike script, not a package — load directly,
# reusing the module test_migrate_ids.py may already have registered
_mod = sys.modules.get("migrate_ids")
if _mod is None:
    _script = Path(__file__).with_name("migrate_ids.py")
    _spec = importlib.util.spec_from_file_location("migrate_ids", _script)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["migrate_ids"] = _mod
    _spec.loader.exec_module(_mod)

plan_migration = _mod.plan_migration
MigrationError = _mod.MigrationError

NOW = datetime(2026, 11, 24, 21, 30, tzinfo=UTC)
RUN = "20261124T213000Z"
NOW2 = datetime(2026, 11, 25, 6, 5, 9, tzinfo=UTC)
RUN2 = "20261125T060509Z"
# summer notes in Europe/Prague: the UTC id is two hours earlier
A, A2 = "20240715100000", "20240715080000"
B, B2 = "20240716100000", "20240716080000"
C, C2 = "20240717100000", "20240717080000"
# July naive notes: each new id is the old id of the next note
CHAIN = ("20240715120000", "20240715100000", "20240715080000", "20240715060000")


def _vault(root: Path) -> Path:
    (root / "vault" / "notes").mkdir(parents=True)
    return (root / "vault").resolve()


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


def _date(stem: str) -> str:
    return f"{stem[:4]}-{stem[4:6]}-{stem[6:8]} {stem[8:10]}:{stem[10:12]}:{stem[12:14]}"


def _note(vault: Path, stem: str) -> Path:
    return _put(vault, f"notes/{stem}.md", _fm(f"id: {stem}", f"date: {_date(stem)}"))


def _migrated(old: str, new: str) -> bytes:
    return _fm(f"id: {new}", f"date: {_date(old)}+02:00")


def _files(vault: Path) -> set[str]:
    return {p.relative_to(vault).as_posix() for p in vault.rglob("*") if p.is_file()}


def _abs(vault: Path, path: Path) -> Path:
    return path if path.is_absolute() else vault / path


def _temps(vault: Path) -> list[Path]:
    return [p for p in vault.rglob("*") if p.name.endswith(".migrating")]


def _entry(vault: Path, old: Path, new: Path, before: bytes, note: tuple = (None,) * 4) -> dict:
    rel_old = old.relative_to(vault).as_posix()
    return {
        "old_path": rel_old,
        "new_path": new.relative_to(vault).as_posix(),
        "temp_path": f"{rel_old}.{RUN}.migrating" if old != new else None,
        "sha256_before": hashlib.sha256(before).hexdigest(),
        "sha256_after": _sha(new),
        "old_id": note[0],
        "new_id": note[1],
        "old_date_line": note[2],
        "new_date_line": note[3],
    }


def _read_map(map_file: Path) -> dict:
    text = map_file.read_text("utf-8")
    data = json.loads(text)
    assert text.rstrip("\n") == json.dumps(data, indent=2, sort_keys=True)
    data["files"] = sorted(data["files"], key=lambda e: e["old_path"])
    return data


def test_apply_rewrites_all_reference_forms(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    a = _note(vault, A)
    b = _put(vault, "notes/f/202401151000.md", _fm("id: 202401151000", "date: 2024-01-15 10:00:00"))
    forms = "[[{a}]] ![[{a}]] [[notes/{a}|a]] [[notes/f/{b}#h]] [[{b}.md]] [[{a}\\|t]]\nkey:: [[{b}]]\n"
    ref_before = _fm(f'up: "[[{A}]]"', body=forms.format(a=A, b="202401151000"))
    ref = _put(vault, "notes/daily/2024-07-15.md", ref_before)
    tpl = _put(vault, "templates/t.md", f"[[{A}]]\n".encode())
    near = _put(vault, "templates/near.md", f"[[{A[:-1]}1]] {A}\n".encode())
    hidden = [_put(vault, ".obsidian/x.md", f"[[{A}]]\n".encode()), _put(vault, ".trash/y.md", b"[[202401151000]]\n")]
    outside = {p: p.read_bytes() for p in (tpl, near, *hidden)}
    a_before, b_before = a.read_bytes(), b.read_bytes()

    result = _mod.apply_migration(plan_migration(vault), tmp_path / "state" / "maps", now=NOW)

    assert ref.read_bytes() == _fm(f'up: "[[{A2}]]"', body=forms.format(a=A2, b="20240115090000"))
    new_a, new_b = vault / "notes" / f"{A2}.md", vault / "notes" / "f" / "20240115090000.md"
    assert new_a.read_bytes() == _migrated(A, A2)
    assert new_b.read_bytes() == _fm("id: 20240115090000", "date: 2024-01-15 10:00:00+01:00")
    assert not a.exists() and not b.exists() and _temps(vault) == []
    # outside notes/ is scanned read-only; .obsidian and .trash are not scanned
    assert {p: p.read_bytes() for p in outside} == outside
    assert [_abs(vault, p) for p in result.outside_references] == [tpl]
    assert result.map_file.resolve() == (tmp_path / "state" / "maps" / f"{RUN}.json").resolve()
    data = _read_map(result.map_file)
    assert {k: v for k, v in data.items() if k != "files"} == {
        "version": 1,
        "vault": str(vault),
        "run_id": RUN,
        "naive_timezone": "Europe/Prague",
    }
    b_note = ("202401151000", "20240115090000", "date: 2024-01-15 10:00:00", "date: 2024-01-15 10:00:00+01:00")
    assert data["files"] == [
        _entry(vault, a, new_a, a_before, (A, A2, f"date: {_date(A)}", f"date: {_date(A)}+02:00")),
        _entry(vault, ref, ref, ref_before),
        _entry(vault, b, new_b, b_before, b_note),
    ]


def test_longer_digit_string_is_not_a_reference(tmp_path: Path) -> None:
    vault = _vault(tmp_path / "one")
    _note(vault, A)
    _put(vault, "notes/202401151000.md", _fm("id: 202401151000", "date: 2024-01-15 10:00:00"))
    misses = (
        f"[[1{A}]] [[{A}1]] [[{A}_a]] [[{A}-other]] [[x{A}]] {A}\n"
        "[[20240115100000]] [[2024011510000]] 202401151000\n"
    )
    ref = _put(vault, "notes/r.md", (f"[[{A}]] [[202401151000]]\n" + misses).encode())

    _mod.apply_migration(plan_migration(vault), tmp_path / "state", now=NOW)

    assert ref.read_bytes() == (f"[[{A2}]] [[20240115090000]]\n" + misses).encode()
    assert _files(vault) == {f"notes/{A2}.md", "notes/20240115090000.md", "notes/r.md"}

    # no renamed note: the already-UTC note only gets its date line, links stay
    other = _vault(tmp_path / "two")
    utc = _put(other, "notes/20240718080000.md", _fm("id: 20240718080000", "date: 2024-07-18 10:00:00"))
    link = _put(other, "notes/r.md", b"[[20240718080000]] [[20240718100000]]\n")

    _mod.apply_migration(plan_migration(other), tmp_path / "state2", now=NOW)

    assert utc.read_bytes() == _fm("id: 20240718080000", "date: 2024-07-18 10:00:00+02:00")
    assert link.read_bytes() == b"[[20240718080000]] [[20240718100000]]\n"


def test_attachment_links_untouched(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    j, j2 = "20240902100000", "20240902080000"
    _note(vault, j)
    svg = _put(vault, f"notes/{j}.svg", b"<svg/>")
    keep = (
        f"![d]({j}.svg) [f](file:///v/notes/{j}.md) <file:///v/notes/{j}.md>\n"
        f"![[{j}.svg]] ![[{j}.png|200]] ![[{j}.svg|300]] [[x|{j}]]\n"
    )
    ref = _put(vault, "notes/r.md", (keep + f"[[{j}]]\n").encode())
    plan = plan_migration(vault)
    assert plan.kept_attachments == (svg,)

    result = _mod.apply_migration(plan, tmp_path / "state", now=NOW)

    assert ref.read_bytes() == (keep + f"[[{j2}]]\n").encode()
    assert svg.read_bytes() == b"<svg/>"
    assert _files(vault) == {f"notes/{j}.svg", f"notes/{j2}.md", "notes/r.md"}
    assert result.map_file.is_file()


def test_code_fences_untouched(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _note(vault, A)
    lf = (
        "```\n[[{a}]]\n````\n[[{x}]] after a longer closer\n"
        "> ```\n> [[{a}]]\n> ```\n"
        "- ```\n  [[{a}]]\n  ```\n"
        "~~~\n[[{a}]]\n~~~\n"
        "`[[{a}]]` and ``[[{a}]]``\n"
        "[[{x}]]\n"
    )
    crlf = "```\r\n[[{a}]]\r\n```\r\n[[{x}]]\r\n> ```\r\n> [[{a}]]\r\n> ```\r\n- [[{x}]]\r\n"
    unclosed = "[[{x}]]\n```\n[[{a}]]\n"
    refs = {
        _put(vault, f"notes/{name}.md", tpl.format(a=A, x=A).encode()): tpl.format(a=A, x=A2).encode()
        for name, tpl in (("lf", lf), ("crlf", crlf), ("unclosed", unclosed))
    }

    _mod.apply_migration(plan_migration(vault), tmp_path / "state", now=NOW)

    assert {p: p.read_bytes() for p in refs} == refs
    assert (vault / "notes" / f"{A2}.md").read_bytes() == _migrated(A, A2)


def _refuse(root: Path, plan: object, map_dir: Path, match: str | None = None) -> None:
    before = _snapshot(root)
    with pytest.raises(MigrationError, match=match) as err:
        _mod.apply_migration(plan, map_dir, now=NOW)
    assert err.value.map_file is None
    assert _snapshot(root) == before


def test_leftover_reference_fails_apply(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _note(vault, A)
    _note(vault, B)
    _put(vault, "notes/ok.md", f"[[x|{A}]] [[{A}-meeting]] [[{A}_a]] ![[{A}.svg]] [[{B}]]\n".encode())
    bad = _put(vault, "notes/bad.md", f"[[{A}]]\n[[{A} ]]\n".encode())
    state = tmp_path / "state"

    _refuse(tmp_path, plan_migration(vault), state, match="bad.md")

    # the same vault without the trailing-space link applies
    bad.write_bytes(f"[[{A}]]\n".encode())
    plan = plan_migration(vault)
    _refuse(tmp_path, plan, vault, match=None)
    _refuse(tmp_path, plan, vault / "notes" / "state", match=None)
    _put(tmp_path, f"state/{RUN}.json", b"{}")
    _refuse(tmp_path, plan, state, match=RUN)
    (state / f"{RUN}.json").unlink()

    # a link that already uses a new stem cannot be reversed
    linked = _put(vault, "notes/new.md", f"[[{A}]] [[{A2}]]\n".encode())
    _refuse(tmp_path, plan_migration(vault), state, match="new.md")
    linked.unlink()

    # drift since the plan: an edit, an added file, a removed file
    plan = plan_migration(vault)
    bad.write_bytes(f"[[{A}]] edited\n".encode())
    _refuse(tmp_path, plan, state, match="bad.md")
    plan = plan_migration(vault)
    added = _put(vault, "notes/added.md", b"text\n")
    _refuse(tmp_path, plan, state, match="added.md")
    plan = plan_migration(vault)
    added.unlink()
    _refuse(tmp_path, plan, state, match="added.md")

    result = _mod.apply_migration(plan_migration(vault), state, now=NOW)

    assert result.map_file.is_file()
    assert bad.read_bytes() == f"[[{A2}]] edited\n".encode()
    assert (vault / "notes" / "ok.md").read_bytes() == (
        f"[[x|{A}]] [[{A}-meeting]] [[{A}_a]] ![[{A}.svg]] [[{B2}]]\n".encode()
    )


def test_undo_restores_bytes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    a = _note(vault, A)
    crlf = _put(vault, f"notes/{B}.md", f"---\r\nid: {B}\r\ndate: {_date(B)}\r\n---\r\nSee [[{A}]].\r\n".encode())
    short = _put(vault, "notes/f/202401151000.md", _fm("id: 202401151000", "date: 2024-01-15 10:00:00"))
    doc = _put(vault, "notes/scan.md", _fm(f"id: {C}", "type: document", body=f"[[{B}]]\n"))
    ref = _put(vault, "notes/daily/d.md", f"[[{A}]] ![[{B}]] [[notes/f/202401151000|s]]\n".encode())
    _put(vault, f"notes/{A}.svg", b"<svg/>")
    original = _snapshot(vault)

    result = _mod.apply_migration(plan_migration(vault), tmp_path / "state", now=NOW)

    assert _snapshot(vault) != original
    report = _mod.undo_migration(vault, result.map_file)

    assert _snapshot(vault) == original
    assert _temps(vault) == []
    notes = vault / "notes"
    pairs = {
        "a": (a, notes / f"{A2}.md"),
        "crlf": (crlf, notes / f"{B2}.md"),
        "short": (short, notes / "f" / "20240115090000.md"),
        "doc": (doc, doc),
        "ref": (ref, ref),
    }
    assert _who(vault, report.restored, pairs) == ["a", "crlf", "doc", "ref", "short"]
    assert (report.unchanged, report.skipped) == ((), ())


    _undo_after_edit(tmp_path / "edited")


def _who(vault: Path, paths: tuple[Path, ...], notes: dict[str, tuple[Path, Path]]) -> list[str]:
    found = [k for p in paths for k, pair in notes.items() if _abs(vault, p) in pair]
    assert len(found) == len(paths)
    return sorted(found)


def _undo_after_edit(root: Path) -> None:
    vault = _vault(root)
    notes = vault / "notes"
    e, o, p = _note(vault, A), _note(vault, B), _note(vault, C)
    both = _put(vault, "notes/both.md", f"[[{A}]] [[{B}]]\n".encode())
    only = _put(vault, "notes/only.md", f"[[{C}]]\n".encode())
    original = _snapshot(vault)
    result = _mod.apply_migration(plan_migration(vault), root / "state", now=NOW)
    edited = _migrated(A, A2) + b"edited\n"
    (notes / f"{A2}.md").write_bytes(edited)

    report = _mod.undo_migration(vault, result.map_file)

    pairs = {
        "e": (e, notes / f"{A2}.md"),
        "o": (o, notes / f"{B2}.md"),
        "p": (p, notes / f"{C2}.md"),
        "both": (both, both),
        "only": (only, only),
    }
    # the referrer of the edited note cannot be reversed, so the other note it links stays too
    assert _who(vault, report.skipped, pairs) == ["both", "e", "o"]
    assert _who(vault, report.restored, pairs) == ["only", "p"]
    assert report.unchanged == ()
    assert (notes / f"{A2}.md").read_bytes() == edited
    assert (notes / f"{B2}.md").read_bytes() == _migrated(B, B2)
    assert both.read_bytes() == f"[[{A2}]] [[{B2}]]\n".encode()
    for stem in re.findall(rb"\[\[(\d+)\]\]", both.read_bytes()):
        assert (notes / f"{stem.decode()}.md").is_file()
    assert (p.read_bytes(), only.read_bytes()) == (original[p], original[only])
    assert not (notes / f"{C2}.md").exists()
    assert not e.exists() and not o.exists()
    assert _temps(vault) == []


def _fail_on(m: pytest.MonkeyPatch, target: object, attr: str, n: int) -> list[tuple]:
    real = getattr(target, attr)
    calls: list[tuple] = []

    def fake(*args: object, **kwargs: object) -> object:
        calls.append(args)
        if len(calls) == n:
            raise OSError(28, "No space left on device")
        return real(*args, **kwargs)

    m.setattr(target, attr, fake)
    return calls


def _two_notes_and_referrer(root: Path) -> Path:
    vault = _vault(root)
    _note(vault, A)
    _note(vault, B)
    _put(vault, "notes/r.md", f"[[{A}]] [[{B}]]\n".encode())
    return vault


def _stop_apply(vault: Path, monkeypatch: pytest.MonkeyPatch, target: object, attr: str, n: int) -> None:
    root = vault.parent
    original = _snapshot(vault)
    plan = plan_migration(vault)
    with monkeypatch.context() as m:
        calls = _fail_on(m, target, attr, n)
        with pytest.raises(MigrationError) as err:
            _mod.apply_migration(plan, root / "state", now=NOW2)
    assert len(calls) == n
    assert err.value.map_file.resolve() == (root / "state" / f"{RUN2}.json").resolve()
    assert _snapshot(vault) != original

    _mod.undo_migration(vault, err.value.map_file)

    assert _snapshot(vault) == original
    assert _temps(vault) == []


def test_stopped_apply_then_undo_restores_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # call 1 writes the map file, call 3 is the second note write of phase B
    _stop_apply(_two_notes_and_referrer(tmp_path / "write"), monkeypatch, _mod, "atomic_write_bytes", 3)

    # phase A of the chain stops after its first rename
    chain = _vault(tmp_path / "chain")
    for stem in CHAIN[:3]:
        _note(chain, stem)
    _put(chain, "notes/r.md", "".join(f"[[{s}]]\n" for s in CHAIN[:3]).encode())
    _stop_apply(chain, monkeypatch, _mod.os, "rename", 2)

    # an undo that stops after its first write is rerun
    undo_root = tmp_path / "undo"
    vault = _two_notes_and_referrer(undo_root)
    original = _snapshot(vault)
    result = _mod.apply_migration(plan_migration(vault), undo_root / "state", now=NOW)
    with monkeypatch.context() as m:
        calls = _fail_on(m, _mod, "atomic_write_bytes", 2)
        with pytest.raises(MigrationError):
            _mod.undo_migration(vault, result.map_file)
    assert len(calls) == 2
    assert _snapshot(vault) != original

    report = _mod.undo_migration(vault, result.map_file)

    assert (len(report.restored), len(report.unchanged), report.skipped) == (2, 1, ())
    assert _snapshot(vault) == original
    assert _temps(vault) == []


def test_chain_and_swap_rename_safely(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    notes = vault / "notes"
    s0, s1, s2, s3 = CHAIN
    for stem in CHAIN[:3]:
        _note(vault, stem)
    x = _note(vault, B)
    # an aware date two hours behind UTC: its new id is the old id of x
    y = _put(vault, f"notes/{B2}.md", _fm(f"id: {B2}", "date: 2024-07-16T08:00:00-02:00"))
    _put(vault, "notes/r.md", "".join(f"[[{s}]]\n" for s in (s0, s1, s2, B, B2)).encode())
    original = _snapshot(vault)
    plan = plan_migration(vault)
    assert [(c.path, c.new_path, c.new_id) for c in plan.changes] == [
        (notes / f"{s2}.md", notes / f"{s3}.md", s3),
        (notes / f"{s1}.md", notes / f"{s2}.md", s2),
        (notes / f"{s0}.md", notes / f"{s1}.md", s1),
        (y, notes / f"{B}.md", B),
        (x, notes / f"{B2}.md", B2),
    ]

    result = _mod.apply_migration(plan, tmp_path / "state", now=NOW)

    assert {p.name: p.read_bytes() for p in notes.iterdir()} == {
        f"{s1}.md": _migrated(s0, s1),
        f"{s2}.md": _migrated(s1, s2),
        f"{s3}.md": _migrated(s2, s3),
        f"{B2}.md": _migrated(B, B2),
        f"{B}.md": _fm(f"id: {B}", "date: 2024-07-16T08:00:00-02:00"),
        "r.md": "".join(f"[[{s}]]\n" for s in (s1, s2, s3, B2, B)).encode(),
    }

    report = _mod.undo_migration(vault, result.map_file)

    assert len(report.restored) == 6
    assert _snapshot(vault) == original
    assert _temps(vault) == []


def test_link_not_rewritten_twice(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    for stem in CHAIN[:3]:
        _note(vault, stem)
    up = 'up: "[[{0}]]"'
    links = "[[{0}]] [[{1}]] [[{1}|again]] [[{2}#h]]\n"
    ref = _put(vault, "notes/r.md", _fm(up.format(*CHAIN), body=links.format(*CHAIN)))
    plan = plan_migration(vault)
    assert plan.reference_count == 5

    _mod.apply_migration(plan, tmp_path / "state", now=NOW)

    # each link moves one step along the chain, never two
    assert ref.read_bytes() == _fm(up.format(*CHAIN[1:]), body=links.format(*CHAIN[1:]))
    again = plan_migration(vault)
    assert (again.changes, again.reference_count) == ((), 0)
    assert len(again.already_utc) == 3


def test_frontmatter_other_bytes_unchanged(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    notes = vault / "notes"
    head = (
        f'---\ntitle: "Café: a note"\nid: "{{}}" # keep\ntags:\n  - x\n'
        f'source_id: {A}\ndate: "{_date(A)}{{}}"  # typed\n'
    )
    tail = f"---\nid: {A}\ndate: {_date(A)}\nno newline at end"
    quoted = _put(vault, f"notes/{A}.md", (head.format(A, "") + tail).encode())
    crlf = _put(vault, f"notes/{B}.md", f"---\r\nid: {B}\r\ntitle: T\r\n---\r\nBody\r\n".encode())
    zulu = _put(vault, f"notes/{C}.md", _fm(f"id: {C}", "date: 2024-07-17T08:00:00Z"))
    in_place = _put(vault, "notes/20240718080000.md", _fm("id: 20240718080000", "date: 2024-07-18 10:00:00"))
    doc_bytes = _fm("id: 20240719100000", "type: document", "date: 2024-07-19 10:00:00")
    doc = _put(vault, "notes/scan.md", doc_bytes)

    result = _mod.apply_migration(plan_migration(vault), tmp_path / "state", now=NOW)

    assert {p.name: p.read_bytes() for p in notes.iterdir()} == {
        f"{A2}.md": (head.format(A2, "+02:00") + tail).encode(),
        f"{B2}.md": f"---\r\nid: {B2}\r\ndate: 2024-07-16T10:00:00+02:00\r\ntitle: T\r\n---\r\nBody\r\n".encode(),
        f"{C2}.md": _fm(f"id: {C2}", "date: 2024-07-17T08:00:00Z"),
        in_place.name: _fm("id: 20240718080000", "date: 2024-07-18 10:00:00+02:00"),
        doc.name: doc_bytes,
    }
    files = {e["old_path"]: e for e in _read_map(result.map_file)["files"]}
    assert sorted(files) == sorted(f"notes/{p.name}" for p in (quoted, crlf, zulu, in_place))
    kept = files[f"notes/{in_place.name}"]
    assert (kept["new_path"], kept["temp_path"]) == (f"notes/{in_place.name}", None)
    assert (kept["old_id"], kept["new_id"]) == ("20240718080000", "20240718080000")
    assert files[f"notes/{B}.md"]["old_date_line"] is None
    assert files[f"notes/{C}.md"]["old_date_line"] == files[f"notes/{C}.md"]["new_date_line"]


def test_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    one = _vault(tmp_path / "one")
    _note(one, A)
    _put(one, "notes/r.md", f"[[{A}]]\n".encode())
    two = _vault(tmp_path / "two")
    _note(two, B)
    before = _snapshot(tmp_path)

    assert _mod.main(["--vault", str(one)]) == 0
    out_one = capsys.readouterr().out
    assert _mod.main(["--vault", str(two)]) == 0
    out_two = capsys.readouterr().out

    assert _snapshot(tmp_path) == before
    assert not (tmp_path / "state").exists()
    # the plan printed is the plan of the vault given with --vault
    assert A2 in out_one and B2 not in out_one
    assert B2 in out_two and A2 not in out_two
