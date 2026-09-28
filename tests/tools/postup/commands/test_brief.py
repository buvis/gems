"""Tests for :mod:`postup.commands.brief` and the bare-``postup`` default path.

The import-isolation test is the risk guard from the PRD: the text brief is the
default surface, so exercising it must not import Textual.
"""

from __future__ import annotations

import json
import sys

from click.testing import CliRunner
from postup.commands.brief.brief import CommandBrief, render_brief
from postup.domain.contracts import CIRun, Commit, PortfolioData, PullRequest, RepoData, write_outputs
from postup.domain.derive import load_view_model
from postup.settings import PostupSettings


def _seed(out_dir, *, enriched: bool = False) -> None:
    repo = RepoData(
        path="/repos/gems",
        owner="buvis",
        name="gems",
        commit_count=5,
        commits=[Commit(sha="abc1234", date="2026-09-01", author="bob", subject="feat: x")],
        prs=[PullRequest(number=1, title="feat", author="bob")],
        ci=[CIRun(workflow="test", status="completed", conclusion="failure", url="u")],
        unreleased_commits=3,
        changelog_unreleased=True,
    )
    data = PortfolioData(generated_at="2026-09-28T10:00:00+00:00", since_days=60, repos=[repo])
    write_outputs(data, out_dir)
    if enriched:
        (out_dir / "epics.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "summary": "Good progress.",
                    "repos": {},
                    "todos": [
                        {
                            "id": "buvis/gems:judgment:x",
                            "repo": "buvis/gems",
                            "kind": "judgment",
                            "urgency": "now",
                            "action": "Ship it",
                            "why": "ready",
                        },
                    ],
                },
            ),
            encoding="utf-8",
        )


class TestMissingData:
    def test_missing_data_json_returns_failure(self, tmp_path):
        result = CommandBrief(PostupSettings(out_dir=str(tmp_path / "out"))).execute()
        assert not result.success
        assert "postup collect" in (result.error or "")


class TestRendering:
    def test_returns_rendered_standup_in_metadata(self, tmp_path):
        out = tmp_path / "out"
        _seed(out)
        result = CommandBrief(PostupSettings(out_dir=str(out))).execute()
        assert result.success
        assert result.metadata["enriched"] is False
        text = result.metadata["text"]
        assert "Portfolio standup" in text
        assert "buvis/gems" in text

    def test_not_enriched_cue_present_without_epics(self, tmp_path):
        out = tmp_path / "out"
        _seed(out)
        vm = load_view_model(out)
        rendered = render_brief(vm)
        assert "not enriched" in rendered
        assert "mechanical:" in rendered

    def test_enriched_shows_summary_and_judgment(self, tmp_path):
        out = tmp_path / "out"
        _seed(out, enriched=True)
        vm = load_view_model(out)
        rendered = render_brief(vm)
        assert "Good progress." in rendered
        assert "judgment:" in rendered
        assert "Ship it" in rendered
        assert "not enriched" not in rendered


class TestImportIsolation:
    def test_bare_postup_does_not_import_textual(self, tmp_path, monkeypatch):
        # The bare `postup` path must stay light: render the default brief and
        # assert Textual was never imported into the process.
        monkeypatch.delenv("BUVIS_POSTUP_ROOTS", raising=False)
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        _seed(tmp_path / "out")

        # Drop any pre-existing textual import so this asserts the brief path,
        # not some earlier test's import.
        for name in [m for m in sys.modules if m == "textual" or m.startswith("textual.")]:
            sys.modules.pop(name, None)

        from postup.adapters.cli import cli

        result = CliRunner().invoke(cli, [])  # bare postup -> brief
        assert result.exit_code == 0
        assert "Portfolio standup" in result.output
        assert "textual" not in sys.modules, "bare `postup` must not import textual"

    def test_brief_subcommand_does_not_import_textual(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        _seed(tmp_path / "out")
        for name in [m for m in sys.modules if m == "textual" or m.startswith("textual.")]:
            sys.modules.pop(name, None)

        from postup.adapters.cli import cli

        result = CliRunner().invoke(cli, ["brief"])
        assert result.exit_code == 0
        assert "textual" not in sys.modules, "`postup brief` must not import textual"
