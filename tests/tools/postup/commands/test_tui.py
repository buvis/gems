"""Tests for :mod:`postup.commands.tui` and the CLI ``tui`` dispatch.

The missing-extra path is exercised without uninstalling Textual by making the
lazy ``from postup.commands.tui.tui import CommandTui`` raise ``ImportError`` —
the CLI must then render ``require_import`` guidance, never a traceback.
"""

from __future__ import annotations

import sys
import types

from click.testing import CliRunner
from postup.commands.tui.tui import CommandTui
from postup.domain.contracts import Commit, PortfolioData, RepoData, write_outputs
from postup.settings import PostupSettings


class _FakeApp:
    """App double recording construction and the run() call."""

    instances: list[_FakeApp] = []

    def __init__(self, view_model: object) -> None:
        self.view_model = view_model
        self.ran = False
        _FakeApp.instances.append(self)

    def run(self) -> None:
        self.ran = True


def _seed(out_dir) -> None:
    repo = RepoData(
        path="/repos/gems",
        owner="buvis",
        name="gems",
        commit_count=5,
        commits=[Commit(sha="abc1234", date="2026-09-01", author="bob", subject="feat: x")],
    )
    write_outputs(PortfolioData(generated_at="2026-09-28T10:00:00+00:00", since_days=60, repos=[repo]), out_dir)


class TestMissingData:
    def test_needs_collect_returns_friendly_failure(self, tmp_path):
        result = CommandTui(PostupSettings(out_dir=str(tmp_path / "out"))).execute()
        assert not result.success
        assert "postup collect" in (result.error or "")


class TestRun:
    def test_success_builds_app_from_view_model_and_runs(self, tmp_path):
        _FakeApp.instances.clear()
        out = tmp_path / "out"
        _seed(out)
        result = CommandTui(PostupSettings(out_dir=str(out)), app_factory=_FakeApp).execute()
        assert result.success
        assert len(_FakeApp.instances) == 1
        app = _FakeApp.instances[0]
        assert app.ran is True
        assert app.view_model.needs_collect is False


class TestMissingExtra:
    def test_missing_textual_extra_yields_require_import_not_traceback(self, tmp_path, monkeypatch):
        # Simulate the 'postup' extra being absent: make the lazy import of
        # CommandTui raise ImportError. The CLI must render install guidance.
        broken = types.ModuleType("postup.commands.tui.tui")  # lacks CommandTui
        monkeypatch.setitem(sys.modules, "postup.commands.tui.tui", broken)
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))

        from postup.adapters.cli import cli

        result = CliRunner().invoke(cli, ["tui"])
        assert result.exit_code == 1  # console.require_import -> panic (exit 1)
        assert "postup" in result.output
        assert "extra" in result.output
        # A friendly install hint, not a Python traceback.
        assert "Traceback" not in result.output
