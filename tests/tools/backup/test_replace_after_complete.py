from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path

import pytest

from backup.capabilities.tar_archive import TarArchive
from backup.config import BackupConfig
from backup.runner import Runner


@pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
class TestReplaceAfterComplete:
    def test_existing_output_is_replaced_only_when_new_archive_is_complete(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        engine: str,
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a").write_text("first contents", encoding="utf-8")
        (source / "b").write_text("second contents", encoding="utf-8")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous complete backup")
        real_replace = os.replace
        published: list[set[str]] = []

        def publish(src: str | Path, dst: str | Path) -> None:
            assert Path(src).parent == out.parent
            assert Path(dst) == out
            assert out.read_bytes() == b"previous complete backup"
            with tarfile.open(src, "r:gz") as archive:
                published.append({member.name for member in archive.getmembers()})
                assert archive.extractfile("src/a").read() == b"first contents"
                assert archive.extractfile("src/b").read() == b"second contents"
            real_replace(src, dst)

        monkeypatch.setattr(os, "replace", publish)
        result = next(iter(TarArchive().run(label="replace", source=str(source), out=str(out), engine=engine)))
        assert result.success is True
        assert result.skipped is False
        assert published == [{"src", "src/a", "src/b"}]
        with tarfile.open(out, "r:gz") as archive:
            assert {member.name for member in archive.getmembers()} == {"src", "src/a", "src/b"}
        assert sorted(path.name for path in tmp_path.iterdir()) == ["out.tar.gz", "src"]

    def test_writer_failure_preserves_previous_bytes_and_removes_temporary_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        engine: str,
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a").write_text("new contents", encoding="utf-8")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous archive bytes")

        def fail(*args: object, **kwargs: object) -> None:
            assert out.read_bytes() == b"previous archive bytes"
            raise OSError("fixture writer failure")

        monkeypatch.setattr(tarfile.TarFile, "add", fail)
        if engine == "system-tar":
            monkeypatch.setattr(subprocess, "Popen", fail)
        cfg = BackupConfig.model_validate(
            {
                "instances": {
                    "replace": {
                        "use": "tar-archive",
                        "with": {
                            "source": str(source),
                            "out": str(out),
                            "engine": engine,
                        },
                    }
                }
            }
        )
        results = list(Runner(cfg).run([("replace", cfg.instances["replace"])]))
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].skipped is False
        assert "fixture writer failure" in results[0].message
        assert out.read_bytes() == b"previous archive bytes"
        assert sorted(path.name for path in tmp_path.iterdir()) == ["out.tar.gz", "src"]
