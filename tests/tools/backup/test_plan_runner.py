from __future__ import annotations

import tarfile
from datetime import datetime
from typing import TYPE_CHECKING

import pytest

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


@pytest.mark.parametrize("mode", ["run", "dry-run", "plan"])
def test_runner_duplicate_groups_reject_all_members_and_keep_independent_outputs(tmp_path: Path, mode: str) -> None:
    shared = tmp_path / "shared.tar.gz"
    second = tmp_path / "second.tar.gz"
    shared.write_bytes(b"keep first group")
    second.write_bytes(b"keep second group")
    groups = {str(shared): ["zinc", "alpha", "beta"], str(second): ["omega", "delta"]}
    outputs = {name: out for out, names in groups.items() for name in names}
    independent = {
        "shared-copy": str(tmp_path / "shared.tar.gz.copy"),
        "prefix-shared": str(tmp_path / "prefix-shared.tar.gz"),
        "other-directory": str(tmp_path / "nested" / "shared.tar.gz"),
    }
    outputs.update(independent)
    cfg = _config(tmp_path, outputs)
    runner = Runner(cfg, dry_run=mode == "dry-run")

    selected = list(cfg.instances.items())
    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))

    assert len(results) == len(outputs)
    assert {result.label for result in results} == set(outputs)
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
                assert result == PlanEntry(
                    result.label, str(tmp_path / "sources" / result.label), str(out), "run", result.reason, False
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
            assert result == PlanEntry(
                result.label, str(tmp_path / "sources" / result.label), str(out), "run", result.reason, False
            )
        else:
            assert result.success is True
            assert result.out_path == str(out)
            _assert_archive(out, result.label)
        assert out.exists() is (mode == "run")
