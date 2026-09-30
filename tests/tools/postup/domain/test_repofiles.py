from __future__ import annotations

from postup.domain.repofiles import (
    read_brush_last_run,
    read_changelog_unreleased,
    read_prd_pipeline,
    read_purge_last_run,
)

_NEW_PRDS = "docs/dev/project-management/prds"
_LEGACY_PRDS = "dev/local/prds"
_NEW_BRUSH = "docs/dev/project-management/audit-results/brush-report.md"
_LEGACY_BRUSH = "dev/local/audit-results/brush-report.md"
_NEW_TRASH = "docs/dev/tmp/.trash"
_LEGACY_TRASH = "dev/local/.trash"


class TestReadPrdPipeline:
    def _seed(self, root, title):
        (root / "backlog").mkdir(parents=True)
        (root / "wip").mkdir()
        (root / "done").mkdir()
        (root / "backlog" / "00063-scaffold.md").write_text(f"# {title}\n\nbody")
        (root / "wip" / "00050-thing.md").write_text("# thing in progress")
        (root / "done" / "00041-atomic.md").write_text("# atomic write")
        (root / "done" / "00042-serve.md").write_text("# serve")

    def test_counts_backlog_wip_done_legacy(self, tmp_path):
        self._seed(tmp_path / _LEGACY_PRDS, "legacy scaffold")

        pipeline = read_prd_pipeline(tmp_path)

        assert pipeline.backlog == ["legacy scaffold"]
        assert [w.title for w in pipeline.wip] == ["thing in progress"]
        assert pipeline.wip[0].idle_days >= 0
        assert pipeline.done_count == 2

    def test_reads_new_location_when_present(self, tmp_path):
        self._seed(tmp_path / _NEW_PRDS, "migrated scaffold")

        pipeline = read_prd_pipeline(tmp_path)

        assert pipeline.backlog == ["migrated scaffold"]
        assert pipeline.done_count == 2

    def test_both_present_reads_new_deterministically(self, tmp_path):
        self._seed(tmp_path / _LEGACY_PRDS, "legacy scaffold")
        self._seed(tmp_path / _NEW_PRDS, "migrated scaffold")

        pipeline = read_prd_pipeline(tmp_path)

        assert pipeline.backlog == ["migrated scaffold"]

    def test_absent_tree_yields_empty(self, tmp_path):
        pipeline = read_prd_pipeline(tmp_path)
        assert pipeline.backlog == []
        assert pipeline.wip == []
        assert pipeline.done_count == 0

    def test_title_falls_back_to_stem(self, tmp_path):
        backlog = tmp_path / _LEGACY_PRDS / "backlog"
        backlog.mkdir(parents=True)
        (backlog / "00099-no-heading.md").write_text("no markdown heading here")
        pipeline = read_prd_pipeline(tmp_path)
        assert pipeline.backlog == ["00099-no-heading"]


class TestReadChangelogUnreleased:
    def test_true_when_unreleased_has_bullets(self, tmp_path):
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n### Added\n\n- a thing\n")
        assert read_changelog_unreleased(tmp_path) is True

    def test_false_when_unreleased_empty(self, tmp_path):
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n## [1.0.0]\n\n- old\n")
        assert read_changelog_unreleased(tmp_path) is False

    def test_none_when_no_changelog(self, tmp_path):
        assert read_changelog_unreleased(tmp_path) is None


class TestReadBrushLastRun:
    def _write(self, path, date):
        report = path
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(f"# Brush report\n\n- generated: {date}\n")

    def test_reads_legacy_generated_date(self, tmp_path):
        self._write(tmp_path / _LEGACY_BRUSH, "2026-09-20")
        assert read_brush_last_run(tmp_path) == "2026-09-20"

    def test_reads_new_location_when_present(self, tmp_path):
        self._write(tmp_path / _NEW_BRUSH, "2026-09-25")
        assert read_brush_last_run(tmp_path) == "2026-09-25"

    def test_both_present_reads_new_deterministically(self, tmp_path):
        self._write(tmp_path / _LEGACY_BRUSH, "2026-09-20")
        self._write(tmp_path / _NEW_BRUSH, "2026-09-25")
        assert read_brush_last_run(tmp_path) == "2026-09-25"

    def test_none_when_no_report(self, tmp_path):
        assert read_brush_last_run(tmp_path) is None

    def test_none_when_no_date_line(self, tmp_path):
        report = tmp_path / _LEGACY_BRUSH
        report.parent.mkdir(parents=True)
        report.write_text("# Brush report\n\nno date here\n")
        assert read_brush_last_run(tmp_path) is None


class TestReadPurgeLastRun:
    def _seed(self, trash_dir, dates):
        trash_dir.mkdir(parents=True, exist_ok=True)
        for date in dates:
            (trash_dir / date).mkdir()

    def test_reads_newest_dated_subdir_new_location(self, tmp_path):
        self._seed(tmp_path / _NEW_TRASH, ["2026-08-01", "2026-09-15", "2026-07-20"])
        assert read_purge_last_run(tmp_path) == "2026-09-15"

    def test_reads_legacy_location(self, tmp_path):
        self._seed(tmp_path / _LEGACY_TRASH, ["2026-06-01", "2026-06-30"])
        assert read_purge_last_run(tmp_path) == "2026-06-30"

    def test_both_present_reads_new_deterministically(self, tmp_path):
        self._seed(tmp_path / _LEGACY_TRASH, ["2026-06-30"])
        self._seed(tmp_path / _NEW_TRASH, ["2026-09-15"])
        assert read_purge_last_run(tmp_path) == "2026-09-15"

    def test_none_when_trash_absent(self, tmp_path):
        assert read_purge_last_run(tmp_path) is None

    def test_none_when_no_dated_subdir(self, tmp_path):
        trash = tmp_path / _NEW_TRASH
        trash.mkdir(parents=True)
        (trash / "notes").mkdir()
        (trash / "2026-09-15.md").write_text("a file, not a dir")
        assert read_purge_last_run(tmp_path) is None
