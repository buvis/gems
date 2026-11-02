from __future__ import annotations

import tarfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from buvis.pybase.result import FatalError

from backup.capabilities.tar_archive import TarArchive
from backup.config import BackupConfig
from backup.runner import Runner
from backup.step_result import PlanEntry

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _config(tmp_path: Path, outputs: dict[str, Path]) -> BackupConfig:
    instances = {}
    for name, out in outputs.items():
        source = tmp_path / "sources" / name
        source.mkdir(parents=True)
        (source / "tiny.txt").write_bytes(name.encode())
        instances[name] = {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}}
    return BackupConfig.model_validate({"instances": instances})


def _fail_metadata(monkeypatch: pytest.MonkeyPatch, errors: dict[Path, Exception]) -> None:
    real_plan = TarArchive.plan

    def plan(capability: TarArchive, **kwargs: object) -> PlanEntry:
        for value in (kwargs.get("source"), kwargs.get("out")):
            if isinstance(value, str) and (error := errors.get(Path(value))) is not None:
                raise error
        return real_plan(capability, **kwargs)

    monkeypatch.setattr(TarArchive, "plan", plan)


def _set_plan_clock(mocker: MockerFixture, now: datetime) -> None:
    clock = mocker.patch("backup.runner.datetime", autospec=True)
    clock.now.return_value = now
    fallback = mocker.patch("backup.capabilities.tar_archive.datetime", autospec=True)
    fallback.now.return_value = datetime(2001, 6, 7, 8, 9, 10)


def _assert_archive(out: Path, name: str) -> None:
    with tarfile.open(out, "r:gz") as archive:
        assert {member.name for member in archive.getmembers() if member.isfile()} == {f"{name}/tiny.txt"}
        member = archive.extractfile(f"{name}/tiny.txt")
        assert member is not None
        assert member.read() == name.encode()


@pytest.mark.parametrize("out", [42, "~/archive-%Y.tar.gz"])
def test_failed_plan_preserves_resolved_source_and_accepts_only_string_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out: object
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = BackupConfig.model_validate(
        {"instances": {"blocked": {"use": "tar-archive", "with": {"source": "~/source", "out": out}}}}
    )
    _fail_metadata(monkeypatch, {Path("~/source"): OSError("metadata unavailable")})

    entry = Runner(cfg)._plan(list(cfg.instances.items()), datetime(2026, 11, 2))[0]

    assert entry.source == str(tmp_path / "source")
    assert entry.out == (str(tmp_path / "archive-2026.tar.gz") if isinstance(out, str) else "")
    assert entry.status == "fail"
    assert "metadata unavailable" in entry.reason


def test_stamp_expansion_failure_does_not_escape_recovery_or_abort_other_instances(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    cfg = _config(tmp_path, {"blocked": tmp_path / "bad-%Y.tar.gz", "independent": tmp_path / "good.tar.gz"})
    clock = mocker.Mock(wraps=datetime(2026, 11, 2))
    clock.strftime.side_effect = ValueError("invalid timestamp pattern")

    entries = Runner(cfg)._plan(list(cfg.instances.items()), clock)

    assert [entry.status for entry in entries] == ["fail", "run"]
    assert "invalid timestamp pattern" in entries[0].reason
    assert entries[0].out == str(tmp_path / "bad-%Y.tar.gz")
    assert entries[1].out == str(tmp_path / "good.tar.gz")


def test_stamp_expansion_failure_keeps_resolved_source_in_failed_plan_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    good_source = tmp_path / "good-source"
    good_source.mkdir()
    (good_source / "tiny.txt").write_bytes(b"good")
    cfg = BackupConfig.model_validate(
        {
            "instances": {
                "blocked": {"use": "tar-archive", "with": {"source": "~/source", "out": "~/bad-%Y.tar.gz"}},
                "independent": {
                    "use": "tar-archive",
                    "with": {"source": str(good_source), "out": str(tmp_path / "good.tar.gz")},
                },
            }
        }
    )
    clock = mocker.Mock(wraps=datetime(2026, 11, 2))
    clock.strftime.side_effect = ValueError("invalid timestamp pattern")

    entries = Runner(cfg)._plan(list(cfg.instances.items()), clock)

    assert [entry.status for entry in entries] == ["fail", "run"]
    assert entries[0].source == str(tmp_path / "source")
    assert entries[0].out == "~/bad-%Y.tar.gz"
    assert "invalid timestamp pattern" in entries[0].reason
    assert entries[1].source == str(good_source)
    assert entries[1].out == str(tmp_path / "good.tar.gz")


def test_tar_archive_exports_public_resolve_paths_that_expands_home_and_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backup.capabilities import tar_archive

    monkeypatch.setenv("HOME", str(tmp_path))

    assert "resolve_paths" in tar_archive.__all__
    source, out = tar_archive.resolve_paths("~/src", "~/out-%Y.tgz", datetime(2026, 11, 2))
    assert isinstance(source, Path)
    assert isinstance(out, Path)
    assert (source, out) == (tmp_path / "src", tmp_path / "out-2026.tgz")
    other_source, other_out = tar_archive.resolve_paths("~/docs", "~/b-%Y.tgz", datetime(2031, 1, 5))
    assert (other_source, other_out) == (tmp_path / "docs", tmp_path / "b-2031.tgz")


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("error_type", [OSError, PermissionError, RuntimeError])
@pytest.mark.parametrize("metadata", ["source", "out"])
def test_runner_isolates_metadata_failures_and_preserves_independent_instances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, error_type: type[Exception], metadata: str
) -> None:
    names = ("before", "blocked", "blocked-copy", "second-blocked", "after")
    outputs = {name: tmp_path / "archives" / name / "daily.tar.gz" for name in names}
    cfg = _config(tmp_path, outputs)
    failed = ("blocked", "second-blocked")
    messages = {name: f"{name}: {metadata} metadata unavailable" for name in failed}
    targets = {name: tmp_path / "sources" / name if metadata == "source" else outputs[name] for name in failed}
    runner = Runner(cfg, dry_run=mode == "dry-run")
    with monkeypatch.context() as patch:
        _fail_metadata(patch, {targets[name]: error_type(messages[name]) for name in failed})
        selected = list(cfg.instances.items())
        results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
    labels = [result.label for result in results]
    if mode == "plan":
        assert labels == list(names)
    else:
        assert sorted(labels) == sorted(names)
        assert labels[: len(failed)] == list(failed)
    for result in results:
        out = outputs[result.label]
        if result.label in failed:
            if mode == "plan":
                assert result.status == "fail"
                assert messages[result.label] in result.reason
            else:
                assert result.success is False
                assert result.skipped is False
                assert messages[result.label] in result.message
            assert not out.exists()
            assert not out.parent.exists()
        else:
            if mode == "plan":
                assert result.status == "run"
                assert result.source == str(tmp_path / "sources" / result.label)
                assert result.out == str(out)
            else:
                assert result.success is True
                assert result.skipped is False
                assert result.out_path == str(out)
            assert out.exists() is (mode == "run")
            assert out.parent.exists() is (mode == "run")
            if mode == "run":
                _assert_archive(out, result.label)


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("error_type", [OSError, PermissionError, RuntimeError])
@pytest.mark.parametrize("metadata", ["source", "out"])
def test_runner_rejects_every_duplicate_output_even_when_member_metadata_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, error_type: type[Exception], metadata: str
) -> None:
    shared = tmp_path / "shared.tar.gz"
    shared.write_bytes(b"keep existing archive")
    colliding = ("blocked", "peer", "another-peer")
    outputs = dict.fromkeys(colliding, shared)
    outputs["blocked-copy"] = tmp_path / "independent" / "shared.tar.gz"
    outputs["suffix-copy"] = tmp_path / "shared.tar.gz.copy"
    cfg = _config(tmp_path, outputs)
    target = tmp_path / "sources" / "blocked" if metadata == "source" else shared
    runner = Runner(cfg, dry_run=mode == "dry-run")
    with monkeypatch.context() as patch:
        _fail_metadata(patch, {target: error_type(f"blocked {metadata} metadata")})
        selected = list(cfg.instances.items())
        results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
    labels = [result.label for result in results]
    if mode == "plan":
        assert labels == list(outputs)
    else:
        assert sorted(labels) == sorted(outputs)
        assert labels[: len(colliding)] == list(colliding)
    for result in results:
        if result.label in colliding:
            others = ", ".join(sorted(name for name in colliding if name != result.label))
            message = f"output '{shared}' is also the output of '{others}'"
            if mode == "plan":
                assert result.status == "fail"
                assert result.reason == message
            else:
                assert result.success is False
                assert result.skipped is False
                assert result.message == message
        else:
            if mode == "plan":
                assert result.status == "run"
                assert result.out == str(outputs[result.label])
            else:
                assert result.success is True
                assert result.out_path == str(outputs[result.label])
            assert outputs[result.label].exists() is (mode == "run")
            if mode == "run":
                _assert_archive(outputs[result.label], result.label)
    assert shared.read_bytes() == b"keep existing archive"
    assert (tmp_path / "independent").exists() is (mode == "run")


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("message", ["backup storage unavailable", "backup permission fatal"])
@pytest.mark.parametrize("metadata", ["source", "out"])
def test_runner_propagates_the_original_fatal_metadata_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, message: str, metadata: str
) -> None:
    out = tmp_path / "notes.tar.gz"
    cfg = _config(tmp_path, {"notes": out})
    fatal = FatalError(message)
    target = tmp_path / "sources" / "notes" if metadata == "source" else out
    runner = Runner(cfg, dry_run=mode == "dry-run")
    with monkeypatch.context() as patch:
        _fail_metadata(patch, {target: fatal})
        with pytest.raises(FatalError) as raised:
            selected = list(cfg.instances.items())
            if mode == "plan":
                runner.plan(selected)
            else:
                list(runner.run(selected))
    assert raised.value is fatal
    assert str(raised.value) == message
    assert not out.exists()


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
def test_runner_keeps_empty_selection_empty_without_planning_unselected_instances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    outputs = {name: tmp_path / "archives" / f"{name}.tar.gz" for name in ("notes", "notes-copy")}
    cfg = _config(tmp_path, outputs)
    errors = {tmp_path / "sources" / name: FatalError(f"unselected {name}") for name in outputs}
    errors.update({out: FatalError(f"unselected output {name}") for name, out in outputs.items()})
    runner = Runner(cfg, dry_run=mode == "dry-run")
    with monkeypatch.context() as patch:
        _fail_metadata(patch, errors)
        results = runner.plan([]) if mode == "plan" else list(runner.run([]))
    assert results == []
    assert not (tmp_path / "archives").exists()
    for name, out in outputs.items():
        assert not out.exists()
        assert (tmp_path / "sources" / name / "tiny.txt").read_bytes() == name.encode()


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("error_type", [OSError, PermissionError, RuntimeError])
@pytest.mark.parametrize("now", [datetime(2026, 12, 31, 23, 59, 59), datetime(2027, 1, 1, 0, 0, 1)])
def test_runner_rejects_timestamp_output_collisions_when_source_metadata_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    mode: str,
    error_type: type[Exception],
    now: datetime,
) -> None:
    pattern = "archive-%Y%m%d-%H%M%S.tar.gz"
    shared = tmp_path / "colliding" / now.strftime(pattern)
    independent = tmp_path / "independent" / "archive.tar.gz"
    cfg = _config(
        tmp_path,
        {
            "stamped": tmp_path / "colliding" / pattern,
            "literal": shared,
            "independent": independent,
        },
    )
    _set_plan_clock(mocker, now)
    runner = Runner(cfg, dry_run=mode == "dry-run")
    with monkeypatch.context() as patch:
        _fail_metadata(patch, {tmp_path / "sources" / "stamped": error_type("stamped source metadata")})
        selected = list(cfg.instances.items())
        results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
    assert [result.label for result in results] == ["stamped", "literal", "independent"]
    for result in results[:2]:
        other = "literal" if result.label == "stamped" else "stamped"
        message = f"output '{shared}' is also the output of '{other}'"
        if mode == "plan":
            assert result.status == "fail"
            assert result.reason == message
            assert result.out == str(shared)
        else:
            assert result.success is False
            assert result.skipped is False
            assert result.message == message
    if mode == "plan":
        assert results[2].status == "run"
        assert results[2].out == str(independent)
    else:
        assert results[2].success is True
        assert results[2].skipped is False
        assert results[2].out_path == str(independent)
    assert not shared.parent.exists()
    assert independent.exists() is (mode == "run")
    assert independent.parent.exists() is (mode == "run")
    if mode == "run":
        _assert_archive(independent, "independent")
