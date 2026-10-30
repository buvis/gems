from __future__ import annotations

import tarfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from buvis.pybase.result import FatalError

from backup.config import BackupConfig
from backup.runner import Runner

if TYPE_CHECKING:
    from os import stat_result


def _config(tmp_path: Path, outputs: dict[str, Path]) -> BackupConfig:
    instances = {}
    for name, out in outputs.items():
        source = tmp_path / "sources" / name
        source.mkdir(parents=True)
        (source / "tiny.txt").write_bytes(name.encode())
        instances[name] = {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}}
    return BackupConfig.model_validate({"instances": instances})


def _fail_metadata(monkeypatch: pytest.MonkeyPatch, errors: dict[Path, Exception]) -> None:
    real_stat = Path.stat

    def stat(path: Path, *, follow_symlinks: bool = True) -> stat_result:
        if path in errors:
            raise errors[path]
        return real_stat(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", stat)


def _assert_archive(out: Path, name: str) -> None:
    with tarfile.open(out, "r:gz") as archive:
        assert {member.name for member in archive.getmembers() if member.isfile()} == {f"{name}/tiny.txt"}
        member = archive.extractfile(f"{name}/tiny.txt")
        assert member is not None
        assert member.read() == name.encode()


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
    assert [result.label for result in results] == list(names)
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
    assert [result.label for result in results] == list(outputs)
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
