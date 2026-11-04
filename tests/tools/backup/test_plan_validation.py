from __future__ import annotations

import tarfile
from typing import TYPE_CHECKING

import pytest
from buvis.pybase.result import FatalError

from backup.capabilities.tar_archive import TarArchive
from backup.config import BackupConfig
from backup.runner import Runner

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

    from backup.step_result import PlanEntry, StepResult


def _source(root: Path, name: str) -> Path:
    source = root / name
    source.mkdir(parents=True)
    (source / "tiny.txt").write_bytes(name.encode())
    (source / "tiny.txt-copy").write_bytes(f"{name}-copy".encode())
    return source


def _invoke(interface: str, mode: str, values: dict[str, object]) -> list[PlanEntry | StepResult]:
    if interface == "capability":
        archive = TarArchive()
        if mode == "plan":
            return [archive.plan(label="selected", **values)]
        return list(archive.run(label="selected", dry_run=mode == "dry-run", **values))
    cfg = BackupConfig.model_validate({"instances": {"selected": {"use": "tar-archive", "with": values}}})
    runner = Runner(cfg, dry_run=mode == "dry-run")
    selected = list(cfg.instances.items())
    return runner.plan(selected) if mode == "plan" else list(runner.run(selected))


def _assert_archive(out: Path, name: str) -> None:
    with tarfile.open(out, "r:gz") as archive:
        files = {member.name for member in archive.getmembers() if member.isfile()}
        assert files == {f"{name}/tiny.txt", f"{name}/tiny.txt-copy"}
        for filename, payload in (("tiny.txt", name), ("tiny.txt-copy", f"{name}-copy")):
            member = archive.extractfile(f"{name}/{filename}")
            assert member is not None
            assert member.read() == payload.encode()


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None for path in root.rglob("*")}


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("name", ["notes", "photos"])
def test_empty_engine_matches_omitted_python_engine(tmp_path: Path, interface: str, mode: str, name: str) -> None:
    source = _source(tmp_path / "sources", name)
    out = tmp_path / "archives" / f"{name}.tar.gz"
    values = {"source": str(source), "out": str(out)}
    omitted = _invoke(interface, "plan", values)
    results = _invoke(interface, mode, {**values, "engine": ""})

    assert len(omitted) == len(results) == 1
    assert omitted[0].status == "run"
    result = results[0]
    assert result.label == "selected"
    if mode == "plan":
        assert result == omitted[0]
        assert result.source == str(source)
        assert result.out == str(out)
        assert result.replaces is False
    else:
        assert result.success is True
        assert result.skipped is False
        assert result.out_path == str(out)
    assert out.exists() is (mode == "run")
    assert out.parent.exists() is (mode == "run")
    if mode == "run":
        _assert_archive(out, name)
    assert (source / "tiny.txt").read_bytes() == name.encode()
    assert (source / "tiny.txt-copy").read_bytes() == f"{name}-copy".encode()


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize(("key", "message"), [("source", "no source configured"), ("out", "no out path configured")])
@pytest.mark.parametrize("existing", [False, True])
def test_empty_paths_fail_without_using_cwd_or_changing_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interface: str, mode: str, key: str, message: str, existing: bool
) -> None:
    source = _source(tmp_path / "sources", "notes")
    cwd = _source(tmp_path, "working")
    monkeypatch.chdir(cwd)
    out = tmp_path / "archives" / "notes.tar.gz"
    if existing:
        out.parent.mkdir()
        out.write_bytes(b"keep existing archive")
    values = {"source": str(source), "out": str(out), key: ""}
    before = _snapshot(tmp_path)

    results = _invoke(interface, mode, values)

    assert len(results) == 1
    result = results[0]
    assert result.label == "selected"
    if mode == "plan":
        assert result.status == "fail"
        assert result.reason == message
        if key == "out":
            assert result.out == ""
            assert result.replaces is False
    else:
        assert result.success is False
        assert result.skipped is False
        assert result.message == message
    assert _snapshot(tmp_path) == before


def _mixed_config(tmp_path: Path) -> tuple[BackupConfig, Path]:
    shared = tmp_path / "shared.tar.gz"
    shared.write_bytes(b"preserve duplicate archive")
    values = {}
    for name in ("empty", "empty-copy", "missing", "missing-copy", "same", "same-copy", "notes", "notes-copy"):
        source = _source(tmp_path / "sources", name)
        out = str(tmp_path / "outputs" / f"{name}.tar.gz")
        if name in {"empty", "empty-copy"}:
            out = ""
        elif name in {"same", "same-copy"}:
            out = str(shared)
        values[name] = {"source": "" if name in {"missing", "missing-copy"} else str(source), "out": out}
    cfg = BackupConfig.model_validate(
        {"instances": {name: {"use": "tar-archive", "with": value} for name, value in values.items()}}
    )
    return cfg, shared


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
def test_runner_keeps_missing_inputs_distinct_from_collisions_and_executes_independent_instances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    cfg, shared = _mixed_config(tmp_path)
    cwd = _source(tmp_path, "working")
    before_cwd = _snapshot(cwd)
    monkeypatch.chdir(cwd)
    runner = Runner(cfg, dry_run=mode == "dry-run")
    selected = list(cfg.instances.items())

    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))

    labels = [result.label for result in results]
    if mode == "plan":
        assert labels == list(cfg.instances)
    else:
        assert sorted(labels) == sorted(cfg.instances)
        assert labels[:-2] == ["empty", "empty-copy", "missing", "missing-copy", "same", "same-copy"]
    for result in results:
        name = result.label
        if name in {"notes", "notes-copy"}:
            assert result.status == "run" if mode == "plan" else result.success is True
            out = tmp_path / "outputs" / f"{name}.tar.gz"
            assert out.exists() is (mode == "run")
            if mode == "run":
                _assert_archive(out, name)
            continue
        message = "no out path configured" if name in {"empty", "empty-copy"} else "no source configured"
        if name in {"same", "same-copy"}:
            other = "same-copy" if name == "same" else "same"
            message = f"output '{shared}' is also the output of '{other}'"
        assert result.status == "fail" if mode == "plan" else result.success is False
        assert (result.reason if mode == "plan" else result.message) == message
    expected = {shared}
    if mode == "run":
        expected |= {tmp_path / "outputs" / f"{name}.tar.gz" for name in ("notes", "notes-copy")}
    assert set(tmp_path.rglob("*.tar.gz")) == expected
    assert shared.read_bytes() == b"preserve duplicate archive"
    assert _snapshot(cwd) == before_cwd
    assert (tmp_path / "outputs").exists() is (mode == "run")


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("engine", ["python-tarfile-copy", "copy-python-tarfile"])
def test_engine_lookalikes_remain_rejected_without_archive_effects(
    tmp_path: Path, interface: str, mode: str, engine: str
) -> None:
    source = _source(tmp_path / "sources", "photos")
    out = tmp_path / "archives" / "photos.tar.gz"
    out.parent.mkdir()
    out.write_bytes(b"preserve rejected engine archive")
    before = _snapshot(tmp_path)

    results = _invoke(interface, mode, {"source": str(source), "out": str(out), "engine": engine})

    assert len(results) == 1
    assert results[0].label == "selected"
    assert results[0].status == "fail" if mode == "plan" else results[0].success is False
    message = results[0].reason if mode == "plan" else results[0].message
    assert f"unknown engine '{engine}'" in message
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("message", ["archive storage unavailable", "archive permission denied"])
def test_fatal_archive_errors_follow_interface_contract_with_empty_default_engine(
    tmp_path: Path, mocker: MockerFixture, interface: str, message: str
) -> None:
    source = _source(tmp_path / "sources", "notes")
    out = tmp_path / "notes.tar.gz"
    mocker.patch("tarfile.open", autospec=True, side_effect=FatalError(message))

    values = {"source": str(source), "out": str(out), "engine": ""}
    if interface == "capability":
        with pytest.raises(FatalError, match=message):
            _invoke(interface, "run", values)
    else:
        results = _invoke(interface, "run", values)
        assert len(results) == 1
        assert results[0].label == "selected"
        assert results[0].success is False
        assert results[0].skipped is False
        assert results[0].message == f"selected failed: {message}"
        assert results[0].archive is None

    assert not out.exists()
    assert (source / "tiny.txt").read_bytes() == b"notes"
    assert (source / "tiny.txt-copy").read_bytes() == b"notes-copy"


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
def test_runner_empty_selection_has_no_archive_effects(tmp_path: Path, mode: str) -> None:
    source = _source(tmp_path / "sources", "unselected")
    cfg = BackupConfig.model_validate(
        {"instances": {"unselected": {"use": "tar-archive", "with": {"source": str(source), "out": ""}}}}
    )
    before = _snapshot(tmp_path)
    runner = Runner(cfg, dry_run=mode == "dry-run")

    results = runner.plan([]) if mode == "plan" else list(runner.run([]))

    assert results == []
    assert _snapshot(tmp_path) == before


def _bundle_source(root: Path) -> Path:
    source = _source(root, "home")
    (source / "data/deep").mkdir(parents=True)
    (source / "data/inner.txt").write_bytes(b"inner")
    (source / "data/deep/leaf.txt").write_bytes(b"leaf")
    return source


def _reason(result: PlanEntry | StepResult, mode: str) -> str:
    return result.reason if mode == "plan" else result.message


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize(
    ("items", "out_rel", "item_rel"),
    [
        (["data"], "data/x.tar.gz", "data"),
        (["tiny.txt", "data/deep"], "data/deep/more/x.tar.gz", "data/deep"),
        (["data"], "data", "data"),
        (["tiny.txt"], "tiny.txt", "tiny.txt"),
    ],
)
def test_bundle_out_inside_selected_item_fails_identically_in_every_mode(
    tmp_path: Path, interface: str, mode: str, items: list[str], out_rel: str, item_rel: str
) -> None:
    source = _bundle_source(tmp_path)
    out = source / out_rel
    if out.parent.is_dir() and not out.exists():
        out.write_bytes(b"previous")
    before = _snapshot(tmp_path)

    (result,) = _invoke(interface, mode, {"source": str(source), "out": str(out), "items": items})

    message = (
        f"out path {out} is inside selected item {source / item_rel}; choose an out path outside the bundle's items"
    )
    assert result.status == "fail" if mode == "plan" else result.success is False
    assert _reason(result, mode) == message
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize(
    ("items", "out_rel", "members"),
    [
        (["tiny.txt"], "backups/x.tar.gz", {"tiny.txt"}),
        (["tiny.txt"], "tiny.txt.tar.gz", {"tiny.txt"}),
        (
            ["data", "tiny.txt-copy"],
            "data-backup.tar.gz",
            {"data", "data/inner.txt", "data/deep", "data/deep/leaf.txt", "tiny.txt-copy"},
        ),
        (["data/deep"], "data/x.tar.gz", {"data/deep", "data/deep/leaf.txt"}),
    ],
)
def test_bundle_out_under_source_outside_items_plans_runs_and_archives_only_items(
    tmp_path: Path, interface: str, mode: str, items: list[str], out_rel: str, members: set[str]
) -> None:
    source = _bundle_source(tmp_path)
    out = source / out_rel
    before = _snapshot(tmp_path)

    (result,) = _invoke(interface, mode, {"source": str(source), "out": str(out), "items": items})

    if mode == "plan":
        assert result.status == "run"
        assert result.reason == ""
        assert result.source == str(source)
        assert result.out == str(out)
        assert result.replaces is False
    else:
        assert result.success is True
        assert result.skipped is False
        assert result.out_path == str(out)
    if mode != "run":
        assert _snapshot(tmp_path) == before
        assert not out.exists()
        return
    with tarfile.open(out, "r:gz") as archive:
        assert {member.name for member in archive.getmembers()} == members


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("extra", [{}, {"items": None}])
def test_whole_tree_out_under_source_keeps_source_message_in_every_mode(
    tmp_path: Path, interface: str, mode: str, extra: dict[str, object]
) -> None:
    source = _bundle_source(tmp_path)
    out = source / "backups/all.tar.gz"
    before = _snapshot(tmp_path)

    (result,) = _invoke(interface, mode, {"source": str(source), "out": str(out), **extra})

    message = f"out path {out} is inside source {source}; choose an out path outside the backup source"
    assert result.status == "fail" if mode == "plan" else result.success is False
    assert _reason(result, mode) == message
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("items", [["data"], ["tiny.txt", "data/deep"]])
def test_bundle_out_equal_to_source_keeps_source_message_in_every_mode(
    tmp_path: Path, interface: str, mode: str, items: list[str]
) -> None:
    source = _bundle_source(tmp_path)
    before = _snapshot(tmp_path)

    (result,) = _invoke(interface, mode, {"source": str(source), "out": str(source), "items": items})

    message = f"out path {source} is inside source {source}; choose an out path outside the backup source"
    assert result.status == "fail" if mode == "plan" else result.success is False
    assert _reason(result, mode) == message
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize(
    ("items", "message"),
    [
        ([], "items must not be empty"),
        (["../x"], "invalid item '../x': must be a relative path inside the source"),
        ("data", "items must be a list of relative paths"),
    ],
)
def test_invalid_items_win_over_containment_in_every_mode(
    tmp_path: Path, interface: str, mode: str, items: object, message: str
) -> None:
    source = _bundle_source(tmp_path)
    out = source / "backups/x.tar.gz"
    before = _snapshot(tmp_path)

    (result,) = _invoke(interface, mode, {"source": str(source), "out": str(out), "items": items})

    assert result.status == "fail" if mode == "plan" else result.success is False
    assert _reason(result, mode) == message
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("mode", ["plan", "run"])
def test_bundle_plan_marks_existing_out_under_source_as_replaced_and_rerun_succeeds(tmp_path: Path, mode: str) -> None:
    source = _bundle_source(tmp_path)
    out = source / "backups/x.tar.gz"
    values = {"source": str(source), "out": str(out), "items": ["tiny.txt"]}
    (first,) = _invoke("capability", "run", values)
    assert first.success is True

    (result,) = _invoke("capability", mode, values)

    if mode == "plan":
        assert result.status == "run"
        assert result.replaces is True
    else:
        assert result.success is True
        with tarfile.open(out, "r:gz") as archive:
            assert [member.name for member in archive.getmembers()] == ["tiny.txt"]
