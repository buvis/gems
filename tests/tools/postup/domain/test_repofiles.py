from __future__ import annotations

from postup.domain.repofiles import (
    read_brush_last_run,
    read_changelog_unreleased,
    read_prd_pipeline,
)


class TestReadPrdPipeline:
    def test_counts_backlog_wip_done(self, tmp_path):
        prds = tmp_path / "dev" / "local" / "prds"
        (prds / "backlog").mkdir(parents=True)
        (prds / "wip").mkdir()
        (prds / "done").mkdir()
        (prds / "backlog" / "00063-scaffold.md").write_text("# postup scaffold\n\nbody")
        (prds / "wip" / "00050-thing.md").write_text("# thing in progress")
        (prds / "done" / "00041-atomic.md").write_text("# atomic write")
        (prds / "done" / "00042-serve.md").write_text("# serve")

        pipeline = read_prd_pipeline(tmp_path)

        assert pipeline.backlog == ["postup scaffold"]
        assert [w.title for w in pipeline.wip] == ["thing in progress"]
        assert pipeline.wip[0].idle_days >= 0
        assert pipeline.done_count == 2

    def test_absent_tree_yields_empty(self, tmp_path):
        pipeline = read_prd_pipeline(tmp_path)
        assert pipeline.backlog == []
        assert pipeline.wip == []
        assert pipeline.done_count == 0

    def test_title_falls_back_to_stem(self, tmp_path):
        backlog = tmp_path / "dev" / "local" / "prds" / "backlog"
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
    def test_reads_generated_date(self, tmp_path):
        report = tmp_path / "dev" / "local" / "audit-results" / "brush-report.md"
        report.parent.mkdir(parents=True)
        report.write_text("# Brush report\n\n- generated: 2026-09-20\n")
        assert read_brush_last_run(tmp_path) == "2026-09-20"

    def test_none_when_no_report(self, tmp_path):
        assert read_brush_last_run(tmp_path) is None

    def test_none_when_no_date_line(self, tmp_path):
        report = tmp_path / "dev" / "local" / "audit-results" / "brush-report.md"
        report.parent.mkdir(parents=True)
        report.write_text("# Brush report\n\nno date here\n")
        assert read_brush_last_run(tmp_path) is None
