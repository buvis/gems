from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from backup.capabilities.tar_archive import TarArchive
from backup.config import BackupConfig
from backup.runner import Runner

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores mode bits")


@pytest.fixture(params=["python-tarfile", "system-tar"])
def engine(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def lock() -> Iterator[list[Path]]:
    locked: list[Path] = []
    yield locked
    for path in locked:
        path.chmod(0o755)


def _config(tmp_path: Path, engine: str) -> tuple[BackupConfig, Path]:
    locked_parent = tmp_path / "locked-parent"
    (locked_parent / "src").mkdir(parents=True)
    (locked_parent / "src" / "secret.txt").write_text("hidden", encoding="utf-8")
    readable = tmp_path / "readable"
    readable.mkdir()
    (readable / "ok.txt").write_text("fine", encoding="utf-8")
    instances = {
        "blocked": {
            "use": "tar-archive",
            "with": {
                "source": str(locked_parent / "src"),
                "out": str(tmp_path / "blocked.tar.gz"),
                "engine": engine,
            },
        },
        "fine": {
            "use": "tar-archive",
            "with": {"source": str(readable), "out": str(tmp_path / "fine.tar.gz"), "engine": engine},
        },
    }
    return BackupConfig.model_validate({"instances": instances}), locked_parent


class TestUnreadableSource:
    def test_run_fails_blocked_source_and_still_archives_readable_instance(
        self,
        tmp_path: Path,
        engine: str,
        lock: list[Path],
    ) -> None:
        cfg, locked_parent = _config(tmp_path, engine)
        locked_parent.chmod(0o000)
        lock.append(locked_parent)
        results = {r.label: r for r in Runner(cfg).run(list(cfg.instances.items()))}
        assert set(results) == {"blocked", "fine"}
        assert results["blocked"].success is False
        assert results["blocked"].skipped is False
        assert "source not found" not in results["blocked"].message
        assert not (tmp_path / "blocked.tar.gz").exists()
        assert results["fine"].success is True
        assert results["fine"].skipped is False
        assert (tmp_path / "fine.tar.gz").is_file()

    def test_plan_marks_blocked_source_fail_not_skip(
        self,
        tmp_path: Path,
        engine: str,
        lock: list[Path],
    ) -> None:
        cfg, locked_parent = _config(tmp_path, engine)
        locked_parent.chmod(0o000)
        lock.append(locked_parent)
        entries = {e.label: e for e in Runner(cfg).plan(list(cfg.instances.items()))}
        assert entries["blocked"].status == "fail"
        assert entries["fine"].status == "run"


class TestUnreadableItem:
    def test_item_under_locked_directory_fails_instead_of_counting_as_missing(
        self,
        tmp_path: Path,
        engine: str,
        lock: list[Path],
    ) -> None:
        source = tmp_path / "src"
        (source / "locked").mkdir(parents=True)
        (source / "locked" / "inner.txt").write_text("inner", encoding="utf-8")
        (source / "present.txt").write_text("here", encoding="utf-8")
        (source / "locked").chmod(0o000)
        lock.append(source / "locked")
        out = tmp_path / "out.tar.gz"
        (result,) = list(
            TarArchive().run(
                label="bundle",
                source=str(source),
                out=str(out),
                engine=engine,
                items=["locked/inner.txt", "present.txt"],
            ),
        )
        assert result.success is False
        assert result.skipped is False
        assert "missing items" not in result.message
        assert "no selected items" not in result.message
        assert not out.exists()

    def test_genuinely_absent_item_still_reports_missing_with_success(self, tmp_path: Path, engine: str) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "present.txt").write_text("here", encoding="utf-8")
        (result,) = list(
            TarArchive().run(
                label="bundle",
                source=str(source),
                out=str(tmp_path / "out.tar.gz"),
                engine=engine,
                items=["absent.txt", "present.txt"],
            ),
        )
        assert result.success is True
        assert result.skipped is False
        assert result.message.endswith("; missing items: absent.txt")
