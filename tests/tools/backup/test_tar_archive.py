from __future__ import annotations

import os
import stat
import tarfile
from pathlib import Path

import pytest

from backup.capabilities.tar_archive import TarArchive


def _tree(root: Path, files: dict[str, str]) -> None:
    """Materialise a file tree under ``root`` from {relpath: content}."""
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _run(source: Path, out: Path, excludes: list[str], *, dry_run: bool = False) -> object:
    results = list(
        TarArchive().run(
            label="git-src",
            source=str(source),
            out=str(out),
            excludes=excludes,
            dry_run=dry_run,
        ),
    )
    assert len(results) == 1
    return results[0]


def _archive_members(archive: Path) -> set[str]:
    with tarfile.open(archive, mode="r:gz") as tar:
        return {member.name for member in tar.getmembers() if member.isfile()}


class TestWalkFilter:
    def test_global_exclude_drops_matching_dirs(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(
            source,
            {
                "repo/main.py": "x",
                "repo/target/artifact.bin": "junk",
                "repo/__pycache__/mod.pyc": "junk",
            },
        )
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, ["target", "__pycache__"])
        members = _archive_members(out)
        assert "src/repo/main.py" in members
        assert not any("target" in m for m in members)
        assert not any("__pycache__" in m for m in members)
        assert result.file_count == 1

    def test_glob_exclude(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.py": "x", "a.pyc": "junk"})
        out = tmp_path / "out.tar.gz"
        _run(source, out, ["*.pyc"])
        members = _archive_members(out)
        assert "src/a.py" in members
        assert "src/a.pyc" not in members


class TestBkpignorePathScoping:
    def test_bang_target_reincludes_only_that_repo(self, tmp_path: Path) -> None:
        """`!target` in repo A's .bkpignore re-includes only A's target/;
        repo B's target/ stays excluded by the global default."""
        source = tmp_path / "src"
        _tree(
            source,
            {
                "repoA/.bkpignore": "!target\n",
                "repoA/target/real_source.rs": "keep me",
                "repoA/main.rs": "x",
                "repoB/target/artifact.rlib": "junk",
                "repoB/main.rs": "y",
            },
        )
        out = tmp_path / "out.tar.gz"
        _run(source, out, ["target"])
        members = _archive_members(out)
        assert "src/repoA/target/real_source.rs" in members
        assert "src/repoB/target/artifact.rlib" not in members
        assert "src/repoA/main.rs" in members
        assert "src/repoB/main.rs" in members
        # the .bkpignore file itself is never archived
        assert not any(m.endswith(".bkpignore") for m in members)

    def test_bare_line_adds_only_under_subtree(self, tmp_path: Path) -> None:
        """A bare line in repo A's .bkpignore adds an exclude for A only."""
        source = tmp_path / "src"
        _tree(
            source,
            {
                "repoA/.bkpignore": "logs\n",
                "repoA/logs/app.log": "junk",
                "repoA/main.py": "x",
                "repoB/logs/app.log": "kept, B has no bkpignore",
            },
        )
        out = tmp_path / "out.tar.gz"
        _run(source, out, [])
        members = _archive_members(out)
        assert "src/repoA/logs/app.log" not in members
        assert "src/repoB/logs/app.log" in members
        assert "src/repoA/main.py" in members

    def test_nested_bkpignore_layers(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(
            source,
            {
                "repo/.bkpignore": "!target\n",
                "repo/target/keep.rs": "keep",
                "repo/sub/.bkpignore": "secret\n",
                "repo/sub/secret/pw.txt": "drop",
                "repo/sub/ok.txt": "keep",
            },
        )
        out = tmp_path / "out.tar.gz"
        _run(source, out, ["target"])
        members = _archive_members(out)
        assert "src/repo/target/keep.rs" in members
        assert "src/repo/sub/ok.txt" in members
        assert not any("secret" in m for m in members)


class TestDryRun:
    def test_dry_run_writes_no_archive(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repo/main.py": "x", "repo/target/j.bin": "junk"})
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, ["target"], dry_run=True)
        assert not out.exists()
        assert result.success is True
        assert result.file_count == 1

    def test_dry_run_counts_and_bytes_match_real_run(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.txt": "hello", "b.txt": "world!!", "target/j": "junk"})
        dry = _run(source, tmp_path / "d.tar.gz", ["target"], dry_run=True)
        assert dry.file_count == 2
        assert dry.total_bytes == len("hello") + len("world!!")
        assert not (tmp_path / "d.tar.gz").exists()

    def test_dry_run_reports_applied_bkpignore(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"repo/.bkpignore": "!target\n", "repo/target/x.rs": "keep"})
        result = _run(source, tmp_path / "d.tar.gz", ["target"], dry_run=True)
        assert "!target" in result.message


class TestArchiveProduction:
    def test_archive_is_chmod_600(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.txt": "x"})
        out = tmp_path / "out.tar.gz"
        _run(source, out, [])
        mode = stat.S_IMODE(out.stat().st_mode)
        assert mode == 0o600

    def test_strftime_stamp_expanded_in_out(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.txt": "x"})
        out_pattern = str(tmp_path / "git-src-%Y.tar.gz")
        result = next(
            iter(
                TarArchive().run(label="git-src", source=str(source), out=out_pattern, excludes=[], dry_run=True),
            ),
        )
        assert "%Y" not in result.out_path
        assert result.out_path.endswith(".tar.gz")

    def test_missing_source_fails_cleanly(self, tmp_path: Path) -> None:
        result = _run(tmp_path / "nope", tmp_path / "out.tar.gz", [])
        assert result.success is False
        assert "source not found" in result.message


class TestAtomicWrite:
    def test_failure_leaves_no_partial_archive(self, tmp_path: Path, mocker) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.txt": "x", "b.txt": "y"})
        out = tmp_path / "out.tar.gz"

        # Simulate a failure mid-archive: tar.add blows up after the temp file
        # is created. The final path must never appear, and no .tmp must linger.
        mocker.patch.object(tarfile.TarFile, "add", side_effect=OSError("disk full"))
        with pytest.raises(OSError, match="disk full"):
            _run(source, out, [])

        assert not out.exists()
        leftovers = list(tmp_path.glob("out.tar.gz*"))
        assert leftovers == [], f"partial file(s) left behind: {leftovers}"


class TestOutInsideSource:
    """FIX C: an out path inside the source tree would re-archive the previous
    archive on the next run (recursive growth); reject it before walking."""

    def test_out_inside_source_fails_no_archive(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.txt": "x"})
        out = source / "backup" / "out.tar.gz"  # inside source
        result = _run(source, out, [])
        assert result.success is False
        assert "inside source" in result.message
        assert not out.exists()

    def test_out_equal_to_source_fails(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.txt": "x"})
        result = _run(source, source, [])
        assert result.success is False
        assert "inside source" in result.message

    def test_out_outside_source_succeeds(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.txt": "x"})
        out = tmp_path / "out.tar.gz"  # sibling of source, outside it
        result = _run(source, out, [])
        assert result.success is True
        assert out.exists()

    def test_stamped_out_inside_source_fails(self, tmp_path: Path) -> None:
        # the stamp expands the basename only; containment is on the parent.
        source = tmp_path / "src"
        _tree(source, {"a.txt": "x"})
        out = source / "git-src-%Y%m%d.tar.gz"
        result = _run(source, out, [])
        assert result.success is False
        assert "inside source" in result.message


class TestWalkOnError:
    """FIX D: an unreadable subtree must fail the step, not be silently skipped
    into a partial archive reported as success."""

    def test_unreadable_subdir_fails_step(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"ok/a.txt": "x", "locked/secret.txt": "y"})
        locked = source / "locked"
        os.chmod(locked, 0o000)
        try:
            # If chmod does not actually block scanning (e.g. running as root),
            # the premise of this test is void — skip rather than false-pass.
            if os.access(locked, os.R_OK | os.X_OK) or (hasattr(os, "geteuid") and os.geteuid() == 0):
                pytest.skip("chmod 000 does not restrict access here (likely root)")
            out = tmp_path / "out.tar.gz"
            # The capability propagates the OSError (os.walk onerror re-raises and
            # the walk no longer papers over scan errors); the Runner's
            # `except Exception -> StepResult(success=False)` turns it into a
            # failed step. The load-bearing guarantee is that the walk does NOT
            # silently produce a partial archive reported as success.
            with pytest.raises(OSError):
                list(
                    TarArchive().run(
                        label="git-src",
                        source=str(source),
                        out=str(out),
                        excludes=[],
                        dry_run=False,
                    ),
                )
            assert not out.exists()
        finally:
            os.chmod(locked, 0o700)

    def test_runner_turns_walk_error_into_failed_step(self, tmp_path: Path) -> None:
        # End-to-end: through the Runner, a walk error becomes a failed StepResult
        # (interface-agnostic — no exception escapes the runner layer).
        from backup.config import BackupConfig
        from backup.runner import Runner

        source = tmp_path / "src"
        _tree(source, {"ok/a.txt": "x", "locked/secret.txt": "y"})
        locked = source / "locked"
        os.chmod(locked, 0o000)
        try:
            if os.access(locked, os.R_OK | os.X_OK) or (hasattr(os, "geteuid") and os.geteuid() == 0):
                pytest.skip("chmod 000 does not restrict access here (likely root)")
            out = tmp_path / "out.tar.gz"
            cfg = BackupConfig.model_validate(
                {"instances": {"git-src": {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}}}},
            )
            results = list(Runner(cfg).run([("git-src", cfg.instances["git-src"])]))
            assert len(results) == 1
            assert results[0].success is False
            assert not out.exists()
        finally:
            os.chmod(locked, 0o700)


class TestStatErrorsPropagate:
    """FIX E: a selected file that cannot be stat()'d is a real error, not a
    silent 0-byte undercount — the suppress is removed."""

    def test_happy_path_sums_input_bytes(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        _tree(source, {"a.txt": "hello", "b.txt": "world!!"})
        result = _run(source, tmp_path / "out.tar.gz", [], dry_run=True)
        assert result.total_bytes == len("hello") + len("world!!")

    def test_suppress_removed_from_walk(self) -> None:
        source_text = (
            Path(__file__).resolve().parents[3] / "src" / "tools" / "backup" / "capabilities" / "tar_archive.py"
        ).read_text(encoding="utf-8")
        # the stat() in the walk must no longer be wrapped in contextlib.suppress
        walk_start = source_text.index("def _walk_tree(")
        walk_end = source_text.index("def _raise_walk_error(")
        walk_body = source_text[walk_start:walk_end]
        assert "file_path.stat().st_size" in walk_body
        assert "contextlib.suppress" not in walk_body


class TestWalkSymlinkConfinement:
    """A directory symlink under source must not have its .bkpignore read, and
    the walk must not descend it (os.walk followlinks=False + explicit skip)."""

    def test_dir_symlink_bkpignore_not_read(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        (source / "repo").mkdir(parents=True)
        (source / "repo" / "main.py").write_text("x", encoding="utf-8")
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / ".bkpignore").write_text("!node_modules\n", encoding="utf-8")
        (outside / "leak.txt").write_text("secret", encoding="utf-8")
        (source / "link").symlink_to(outside, target_is_directory=True)
        out = tmp_path / "out.tar.gz"
        result = next(
            iter(TarArchive().run(label="t", source=str(source), out=str(out), excludes=[], dry_run=True)),
        )
        # the outside .bkpignore's rule must not appear in applied rules
        assert "!node_modules" not in (result.message or "")
        assert result.success is True
