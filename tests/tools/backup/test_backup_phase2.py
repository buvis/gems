from __future__ import annotations

import tarfile
from pathlib import Path
from unittest.mock import patch

from backup.capabilities.tar_archive import TarArchive
from backup.cli import cli
from backup.config import BackupConfig


def _tree(root: Path, files: dict[str, str]) -> None:
    """Materialise a file tree under ``root`` from {relpath: content}."""
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _archive_members(archive: Path) -> set[str]:
    with tarfile.open(archive, mode="r:gz") as tar:
        return {member.name for member in tar.getmembers() if member.isfile()}


def _run_engine(source: Path, out: Path, engine: str) -> object:
    results = list(
        TarArchive().run(
            label="git-src",
            source=str(source),
            out=str(out),
            excludes=["target"],
            engine=engine,
            dry_run=False,
        ),
    )
    assert len(results) == 1
    return results[0]


def _cfg(instances: dict[str, dict[str, object]], excludes: tuple[str, ...] = ()) -> BackupConfig:
    return BackupConfig.model_validate({"instances": instances, "excludes": list(excludes)})


class TestSourceOutOverride:
    def test_source_and_out_override_selected_instance(self, runner, tmp_path: Path) -> None:
        source = tmp_path / "adhoc"
        _tree(source, {"note.txt": "x"})
        out = tmp_path / "adhoc.tar.gz"
        cfg = _cfg({"git-src": {"use": "tar-archive", "with": {"source": "/cfg/src", "out": "/cfg/out.tgz"}}})
        captured: dict[str, object] = {}

        def _fake_run(self, selected):
            name, instance = selected[0]
            captured["with_"] = dict(instance.with_)
            return iter([])

        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch("backup.runner.Runner.run", _fake_run),
        ):
            result = runner.invoke(cli, ["--only", "git-src", "--source", str(source), "--out", str(out)])
        assert result.exit_code == 0
        assert captured["with_"] == {"source": str(source), "out": str(out)}

    def test_flag_wins_over_config_value(self, runner, tmp_path: Path) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive", "with": {"source": "/cfg/src", "out": "/cfg/out.tgz"}}})
        captured: dict[str, object] = {}

        def _fake_run(self, selected):
            captured["with_"] = dict(selected[0][1].with_)
            return iter([])

        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch("backup.runner.Runner.run", _fake_run),
        ):
            result = runner.invoke(cli, ["--only", "git-src", "--source", str(tmp_path / "s")])
        assert result.exit_code == 0
        # source overridden, out left at its configured value
        assert captured["with_"]["source"] == str(tmp_path / "s")
        assert captured["with_"]["out"] == "/cfg/out.tgz"

    def test_multiple_instances_with_override_is_usage_error(self, runner) -> None:
        cfg = _cfg({"a": {"use": "tar-archive"}, "b": {"use": "tar-archive"}})
        plan = [("a", cfg.instances["a"]), ("b", cfg.instances["b"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.run") as mock_run,
        ):
            result = runner.invoke(cli, ["--source", "/some/dir"])
        assert result.exit_code == 0
        assert "exactly one selected instance" in result.output
        assert mock_run.call_count == 0


class TestShowExcludes:
    def test_show_excludes_for_reflects_unignore(self, runner, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repoA/.bkpignore": "!target\n", "repoA/target/keep.rs": "x"})
        cfg = _cfg(
            {"git-src": {"use": "tar-archive", "with": {"source": str(source), "out": "/x.tgz"}}},
            excludes=("target", "node_modules"),
        )
        with patch("backup.config.load_config", return_value=cfg):
            result = runner.invoke(
                cli,
                ["--show-excludes", "git-src", "--for", str(source / "repoA" / "target")],
            )
        assert result.exit_code == 0
        assert "target" in result.output
        assert "node_modules" in result.output
        assert "!target" in result.output

    def test_show_excludes_writes_no_archive(self, runner, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repoA/main.rs": "x"})
        out = tmp_path / "should-not-exist.tar.gz"
        cfg = _cfg(
            {"git-src": {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}}},
            excludes=("target",),
        )
        with patch("backup.config.load_config", return_value=cfg):
            result = runner.invoke(cli, ["--show-excludes", "git-src", "--for", str(source / "repoA")])
        assert result.exit_code == 0
        assert not out.exists()

    def test_show_excludes_without_for_prints_global_and_note(self, runner, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repoA/main.rs": "x"})
        cfg = _cfg(
            {"git-src": {"use": "tar-archive", "with": {"source": str(source), "out": "/x.tgz"}}},
            excludes=("target", "dist"),
        )
        with patch("backup.config.load_config", return_value=cfg):
            result = runner.invoke(cli, ["--show-excludes", "git-src"])
        assert result.exit_code == 0
        assert "target" in result.output
        assert "dist" in result.output
        assert ".bkpignore rules omitted" in result.output


class TestSystemTarEngine:
    def test_system_tar_member_names_match_python_engine(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(
            source,
            {
                "repoA/.bkpignore": "!target\n",
                "repoA/target/keep.rs": "keep",
                "repoA/main.rs": "x",
                "repoB/target/junk.rlib": "drop",
                "repoB/main.rs": "y",
            },
        )
        py_out = tmp_path / "py.tar.gz"
        sys_out = tmp_path / "sys.tar.gz"
        py_result = _run_engine(source, py_out, "python-tarfile")
        sys_result = _run_engine(source, sys_out, "system-tar")
        assert py_result.success is True
        assert sys_result.success is True
        assert _archive_members(sys_out) == _archive_members(py_out)

    def test_missing_tar_falls_back_to_python_with_note(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repoA/main.rs": "x"})
        out = tmp_path / "out.tar.gz"
        with patch("backup.capabilities.tar_archive.shutil.which", return_value=None):
            result = _run_engine(source, out, "system-tar")
        assert result.success is True
        assert out.exists()
        assert "used python engine" in result.message
        assert "src/repoA/main.rs" in _archive_members(out)

    def test_failing_tar_falls_back_to_python_with_note(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repoA/main.rs": "x"})
        out = tmp_path / "out.tar.gz"

        class _Failed:
            returncode = 2
            stderr = "tar: bogus flag\n"

        with patch("backup.capabilities.tar_archive.subprocess.run", return_value=_Failed()):
            result = _run_engine(source, out, "system-tar")
        assert result.success is True
        assert out.exists()
        assert "used python engine" in result.message
        assert "src/repoA/main.rs" in _archive_members(out)


class TestV1Regression:
    def test_no_flags_behaves_as_v1(self, runner, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repo/main.py": "x", "repo/target/j.bin": "junk"})
        out = tmp_path / "out.tar.gz"
        cfg = _cfg(
            {"git-src": {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}}},
            excludes=("target",),
        )
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert out.exists()
        members = _archive_members(out)
        assert "src/repo/main.py" in members
        assert not any("target" in m for m in members)

    def test_default_engine_unset_matches_v1_output(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repo/main.py": "x", "repo/target/j.bin": "junk"})
        out = tmp_path / "out.tar.gz"
        # engine input defaults to python-tarfile; unset behaves identically
        results = list(
            TarArchive().run(label="git-src", source=str(source), out=str(out), excludes=["target"]),
        )
        assert len(results) == 1
        assert results[0].success is True
        members = _archive_members(out)
        assert "src/repo/main.py" in members
        assert not any("target" in m for m in members)
