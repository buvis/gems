from __future__ import annotations

import tarfile
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from buvis.pybase.result import FatalError

from backup.capabilities.tar_archive import TarArchive
from backup.config import BackupConfig
from backup.runner import Runner
from backup.step_result import PlanEntry

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def _config(tmp_path: Path, outputs: dict[str, str]) -> BackupConfig:
    instances = {}
    for name, out in outputs.items():
        source = tmp_path / "sources" / name
        source.mkdir(parents=True)
        (source / "tiny.txt").write_bytes(name.encode())
        instances[name] = {"use": "tar-archive", "with": {"source": str(source), "out": out}}
    return BackupConfig.model_validate({"instances": instances})


def _assert_archive(out: Path, name: str) -> None:
    with tarfile.open(out, "r:gz") as archive:
        assert {member.name for member in archive.getmembers() if member.isfile()} == {f"{name}/tiny.txt"}
        member = archive.extractfile(f"{name}/tiny.txt")
        assert member is not None
        assert member.read() == name.encode()


def _record_archive_creation(monkeypatch: pytest.MonkeyPatch) -> list[tarfile.TarFile]:
    opened = []
    real_open = tarfile.open

    def record_open(*args: object, **kwargs: object) -> tarfile.TarFile:
        archive = real_open(*args, **kwargs)
        opened.append(archive)
        return archive

    monkeypatch.setattr(tarfile, "open", record_open)
    return opened


@pytest.mark.parametrize("mode", ["run", "dry-run", "plan"])
def test_runner_duplicate_groups_reject_all_members_and_keep_independent_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    shared = tmp_path / "shared.tar.gz"
    second = tmp_path / "second.tar.gz"
    shared.write_bytes(b"keep first group")
    second.write_bytes(b"keep second group")
    groups = {str(shared): ["zinc", "alpha", "beta", "gamma"], str(second): ["omega", "delta"]}
    outputs = {name: out for out, names in groups.items() for name in names}
    independent = {
        "shared-copy": str(tmp_path / "shared.tar.gz.copy"),
        "prefix-shared": str(tmp_path / "prefix-shared.tar.gz"),
        "other-directory": str(tmp_path / "nested" / "shared.tar.gz"),
    }
    outputs.update(independent)
    cfg = _config(tmp_path, outputs)
    missing = tmp_path / "sources" / "gamma"
    (missing / "tiny.txt").unlink()
    missing.rmdir()
    runner = Runner(cfg, dry_run=mode == "dry-run")
    opened = _record_archive_creation(monkeypatch)
    selected = list(cfg.instances.items())
    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
    created = [[member.name for member in archive.members if member.isfile()] for archive in opened]
    assert len(results) == len(outputs)
    assert [result.label for result in results] == list(outputs)
    assert created == ([[f"{name}/tiny.txt"] for name in independent] if mode == "run" else [])
    for result in results:
        if result.label in independent:
            assert result.status == "run" if mode == "plan" else result.success is True
            out = tmp_path / independent[result.label]
            assert out.exists() is (mode == "run")
            if mode == "run":
                _assert_archive(out, result.label)
            continue
        out = outputs[result.label]
        others = ", ".join(sorted(name for name in groups[out] if name != result.label))
        message = f"output '{out}' is also the output of '{others}'"
        if mode == "plan":
            assert result == PlanEntry(
                result.label, str(tmp_path / "sources" / result.label), out, "fail", message, True
            )
        else:
            assert result.success is False
            assert result.message == message
    assert shared.read_bytes() == b"keep first group"
    assert second.read_bytes() == b"keep second group"
    assert (tmp_path / "nested").exists() is (mode == "run")


@pytest.mark.parametrize("mode", ["run", "dry-run", "plan"])
@pytest.mark.parametrize("filename", ["daily.tar.gz", "monthly.tgz"])
def test_runner_duplicate_comparison_expands_home_and_normalizes_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, filename: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    out = home / filename
    out.write_bytes(b"keep normalized collision")
    outputs = {"tilde": f"~/{filename}", "normalized": f"{home}/unused/../{filename}"}
    outputs["near-match"] = str(home / "other" / filename)
    cfg = _config(tmp_path, outputs)
    runner = Runner(cfg, dry_run=mode == "dry-run")

    selected = list(cfg.instances.items())
    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))

    assert len(results) == 3
    assert {result.label for result in results} == set(outputs)
    for result in results:
        if result.label == "near-match":
            assert result.status == "run" if mode == "plan" else result.success is True
            continue
        other = "normalized" if result.label == "tilde" else "tilde"
        message = f"output '{out}' is also the output of '{other}'"
        if mode == "plan":
            assert result.status == "fail"
            assert result.reason == message
        else:
            assert result.success is False
            assert result.message == message
    assert out.read_bytes() == b"keep normalized collision"
    independent = home / "other" / filename
    assert independent.exists() is (mode == "run")
    assert independent.parent.exists() is (mode == "run")
    if mode == "run":
        _assert_archive(independent, "near-match")


@pytest.mark.parametrize("mode", ["run", "dry-run", "plan"])
@pytest.mark.parametrize("now", [datetime(2026, 12, 31, 23, 59, 59), datetime(2027, 1, 1, 0, 0, 1)])
def test_runner_duplicate_guard_compares_timestamp_expanded_outputs(
    tmp_path: Path, mocker: MockerFixture, mode: str, now: datetime
) -> None:
    filename = now.strftime("archive-%Y%m%d-%H%M%S.tar.gz")
    out = tmp_path / filename
    outputs = {"stamped": str(tmp_path / "archive-%Y%m%d-%H%M%S.tar.gz"), "literal": str(out)}
    cfg = _config(tmp_path, outputs)
    clock = mocker.patch("backup.runner.datetime", autospec=True)
    clock.now.return_value = now
    fallback = mocker.patch("backup.capabilities.tar_archive.datetime", autospec=True)
    fallback.now.return_value = datetime(2001, 6, 7, 8, 9, 10)
    runner = Runner(cfg, dry_run=mode == "dry-run")
    selected = list(cfg.instances.items())

    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))

    assert len(results) == 2
    assert {result.label for result in results} == {"stamped", "literal"}
    for result in results:
        other = "literal" if result.label == "stamped" else "stamped"
        message = f"output '{out}' is also the output of '{other}'"
        if mode == "plan":
            assert result.status == "fail"
            assert result.reason == message
            assert result.out == str(out)
        else:
            assert result.success is False
            assert result.message == message
    assert list(tmp_path.glob("*.tar.gz")) == []


@pytest.mark.parametrize("mode", ["run", "dry-run", "plan"])
def test_runner_duplicate_guard_considers_only_selected_instances(tmp_path: Path, mode: str) -> None:
    outputs = {"chosen": str(tmp_path / "shared.tar.gz"), "unchosen": str(tmp_path / "shared.tar.gz")}
    outputs["chosen-copy"] = str(tmp_path / "shared-copy.tar.gz")
    cfg = _config(tmp_path, outputs)
    selected = [(name, cfg.instances[name]) for name in ("chosen", "chosen-copy")]
    runner = Runner(cfg, dry_run=mode == "dry-run")

    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))

    assert len(results) == 2
    assert {result.label for result in results} == {"chosen", "chosen-copy"}
    for result in results:
        assert result.status == "run" if mode == "plan" else result.success is True
        out = tmp_path / outputs[result.label]
        assert out.exists() is (mode == "run")
        if mode == "run":
            _assert_archive(out, result.label)


@pytest.mark.parametrize("mode", ["run", "dry-run", "plan"])
def test_runner_empty_selection_returns_no_steps_and_creates_no_output(tmp_path: Path, mode: str) -> None:
    out = tmp_path / "unselected.tar.gz"
    cfg = _config(tmp_path, {"unselected": str(out)})
    runner = Runner(cfg, dry_run=mode == "dry-run")

    results = runner.plan([]) if mode == "plan" else list(runner.run([]))

    assert results == []
    assert not out.exists()
    assert (tmp_path / "sources" / "unselected" / "tiny.txt").read_bytes() == b"unselected"


@pytest.mark.parametrize("modes", [("run", "plan", "run"), ("plan", "run", "plan")])
@pytest.mark.parametrize("dry_run", [False, True])
def test_runner_shares_one_clock_per_call_and_refreshes_between_run_and_plan(
    tmp_path: Path, mocker: MockerFixture, modes: tuple[str, ...], dry_run: bool
) -> None:
    names = ("notes", "photos")
    pattern = "%Y%m%d-%H%M%S-literal-%%Y.tgz"
    cfg = _config(tmp_path, {name: str(tmp_path / f"{name}-{pattern}") for name in names})
    ticks = [
        datetime(2026, 12, 31, 23, 59, 59),
        datetime(2027, 1, 1, 0, 0, 1),
        datetime(2028, 2, 29, 3, 4, 5),
    ]
    clock = mocker.patch("backup.runner.datetime", autospec=True)
    clock.now.side_effect = ticks
    fallback = mocker.patch("backup.capabilities.tar_archive.datetime", autospec=True)
    fallback.now.return_value = datetime(2001, 6, 7, 8, 9, 10)
    runner = Runner(cfg, dry_run=dry_run)
    written = set()

    for mode, now in zip(modes, ticks, strict=True):
        selected = list(cfg.instances.items())
        results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
        assert len(results) == 2
        assert {result.label for result in results} == set(names)
        for result in results:
            out = tmp_path / f"{result.label}-{now.strftime(pattern)}"
            if mode == "plan":
                expected = TarArchive().plan(label=result.label, now=now, **cfg.instances[result.label].with_)
                assert result == PlanEntry(
                    result.label, str(tmp_path / "sources" / result.label), str(out), "run", expected.reason, False
                )
            else:
                assert result.success is True
                assert result.out_path == str(out)
            assert out.exists() is (mode == "run" and not dry_run)
            if mode == "run" and not dry_run:
                _assert_archive(out, result.label)
                written.add(out)
    assert set(tmp_path.glob("*.tgz")) == written


@pytest.mark.parametrize("mode", ["run", "plan"])
@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        ({"engine": "copy-system-tar"}, "unknown engine 'copy-system-tar'"),
        ({"engine": "python-tarfile-copy"}, "unknown engine 'python-tarfile-copy'"),
    ],
)
def test_runner_preserves_capability_inputs_and_surfaces_validation_failures(
    tmp_path: Path, mode: str, invalid: dict[str, object], message: str
) -> None:
    outputs = {name: str(tmp_path / f"{name}.tar.gz") for name in ("notes", "notes-copy", "invalid")}
    cfg = _config(tmp_path, outputs)
    cfg.instances["invalid"].with_.update(invalid)
    runner = Runner(cfg)

    selected = list(cfg.instances.items())
    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))

    assert len(results) == 3
    assert {result.label for result in results} == set(outputs)
    for result in results:
        out = tmp_path / outputs[result.label]
        if result.label == "invalid":
            assert result.status == "fail" if mode == "plan" else result.success is False
            assert message in (result.reason if mode == "plan" else result.message)
            assert not out.exists()
            continue
        if mode == "plan":
            expected = TarArchive().plan(label=result.label, **cfg.instances[result.label].with_)
            assert result == PlanEntry(
                result.label, str(tmp_path / "sources" / result.label), str(out), "run", expected.reason, False
            )
        else:
            assert result.success is True
            assert result.out_path == str(out)
            _assert_archive(out, result.label)
        assert out.exists() is (mode == "run")


@pytest.mark.parametrize("inherit", [False, True])
def test_runner_preserves_global_and_instance_exclusion_rules(tmp_path: Path, inherit: bool) -> None:
    names = ("notes", "photos")
    outputs = {name: str(tmp_path / f"{name}.tar.gz") for name in names}
    _config(tmp_path, outputs)
    instances = {
        name: {
            "use": "tar-archive",
            "inherit_excludes": inherit,
            "exclude_remove": ["restored"],
            "exclude_add": ["local-drop"],
            "with": {"source": str(tmp_path / "sources" / name), "out": out},
        }
        for name, out in outputs.items()
    }
    cfg = BackupConfig.model_validate({"instances": instances, "excludes": ["global-drop", "restored"]})
    folders = ("global-drop", "restored", "local-drop", "global-drop-copy", "local-drop-copy")
    for name in names:
        for folder in folders:
            path = tmp_path / "sources" / name / folder / "data.txt"
            path.parent.mkdir()
            path.write_bytes(f"{name}/{folder}".encode())

    results = list(Runner(cfg).run(list(cfg.instances.items())))

    assert [result.label for result in results] == list(names)
    kept = {"restored", "global-drop-copy", "local-drop-copy"}
    if not inherit:
        kept.add("global-drop")
    for result in results:
        assert result.success is True
        with tarfile.open(outputs[result.label], "r:gz") as archive:
            expected = {f"{result.label}/{folder}/data.txt" for folder in kept} | {f"{result.label}/tiny.txt"}
            assert {member.name for member in archive.getmembers() if member.isfile()} == expected
            for folder in kept:
                member = archive.extractfile(f"{result.label}/{folder}/data.txt")
                assert member is not None
                assert member.read() == f"{result.label}/{folder}".encode()


def test_runner_preserves_multiple_literal_items_without_archiving_lookalikes(tmp_path: Path) -> None:
    outputs = {name: str(tmp_path / f"{name}.tar.gz") for name in ("notes", "photos")}
    cfg = _config(tmp_path, outputs)
    for name, instance in cfg.instances.items():
        instance.with_["items"] = ["tiny.txt", "folder/child.txt"]
        source = tmp_path / "sources" / name
        (source / "folder").mkdir()
        (source / "folder" / "child.txt").write_bytes(f"{name}-child".encode())
        (source / "folder" / "child.txt-copy").write_bytes(b"exclude nested lookalike")
        (source / "tiny.txt-copy").write_bytes(b"exclude root lookalike")

    results = list(Runner(cfg).run(list(cfg.instances.items())))

    assert [result.label for result in results] == list(outputs)
    for result in results:
        assert result.success is True
        with tarfile.open(outputs[result.label], "r:gz") as archive:
            members = {member.name for member in archive.getmembers() if member.isfile()}
            assert members == {"tiny.txt", "folder/child.txt"}
            for path, payload in (("tiny.txt", result.label), ("folder/child.txt", f"{result.label}-child")):
                member = archive.extractfile(path)
                assert member is not None
                assert member.read() == payload.encode()


@pytest.mark.parametrize("message", ["archive storage unavailable", "archive permission denied"])
def test_runner_propagates_fatal_archive_filesystem_errors(tmp_path: Path, mocker: MockerFixture, message: str) -> None:
    cfg = _config(tmp_path, {"notes": str(tmp_path / "notes.tar.gz")})
    mocker.patch("tarfile.open", autospec=True, side_effect=FatalError(message))

    with pytest.raises(FatalError, match=message):
        list(Runner(cfg).run(list(cfg.instances.items())))


@pytest.mark.parametrize("mode", ["run", "dry-run", "plan"])
def test_runner_preserves_missing_source_skips_and_existing_outputs(tmp_path: Path, mode: str) -> None:
    outputs = {name: str(tmp_path / f"{name}.tar.gz") for name in ("absent", "absent-copy")}
    cfg = _config(tmp_path, outputs)
    for name, out in outputs.items():
        source = tmp_path / "sources" / name
        (source / "tiny.txt").unlink()
        source.rmdir()
        (tmp_path / out).write_bytes(name.encode())
    runner = Runner(cfg, dry_run=mode == "dry-run")
    selected = list(cfg.instances.items())

    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))

    assert [result.label for result in results] == list(outputs)
    for result in results:
        expected = TarArchive().plan(label=result.label, **cfg.instances[result.label].with_)
        assert expected.status == "skip"
        assert expected.reason == f"source not found: {tmp_path / 'sources' / result.label}"
        if mode == "plan":
            assert result == expected
        else:
            assert result.skipped is True
            assert "source not found" in result.message
        assert (tmp_path / outputs[result.label]).read_bytes() == result.label.encode()


@pytest.mark.parametrize("engines", [("python-tarfile", "system-tar"), ("system-tar", "python-tarfile")])
def test_runner_preserves_supported_engine_choices_and_fallback_messages(
    tmp_path: Path, mocker: MockerFixture, engines: tuple[str, str]
) -> None:
    outputs = {name: str(tmp_path / f"{name}.tar.gz") for name in ("notes", "photos")}
    cfg = _config(tmp_path, outputs)
    for instance, engine in zip(cfg.instances.values(), engines, strict=True):
        instance.with_["engine"] = engine
    mocker.patch("backup.capabilities.tar_archive.shutil.which", autospec=True, return_value=None)

    results = list(Runner(cfg).run(list(cfg.instances.items())))

    assert [result.label for result in results] == list(outputs)
    for result, engine in zip(results, engines, strict=True):
        assert result.success is True
        assert ("used python engine" in result.message) is (engine == "system-tar")
        assert result.out_path == outputs[result.label]
        _assert_archive(tmp_path / outputs[result.label], result.label)
