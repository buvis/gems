from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from buvis.pybase.adapters.uv.uv_tool import UvToolManager


@pytest.fixture
def mock_ensure_uv():
    """Mock UvAdapter.ensure_uv to skip uv installation check."""
    with patch("buvis.pybase.adapters.uv.uv_tool.UvAdapter.ensure_uv") as mock:
        yield mock


@pytest.fixture
def mock_console():
    """Mock console output methods."""
    with patch("buvis.pybase.adapters.uv.uv_tool.console") as mock:
        yield mock


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for command execution."""
    with patch("subprocess.run") as mock:
        mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        yield mock


class TestUvToolManager:
    """Tests for UvToolManager."""

    def test_installs_projects_with_pyproject_toml(self, mock_ensure_uv, mock_console, mock_subprocess_run, tmp_path):
        """Should call install_tool for each dir with pyproject.toml."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create two projects with pyproject.toml
        for name in ["pkg_a", "pkg_b"]:
            project = src_dir / name
            project.mkdir()
            (project / "pyproject.toml").write_text("[project]")

        with patch.object(UvToolManager, "install_tool") as mock_install:
            UvToolManager.install_all(tmp_path)

        assert mock_install.call_count == 2
        mock_ensure_uv.assert_called_once()

    def test_skips_directories_without_pyproject(self, mock_ensure_uv, mock_console, tmp_path):
        """Should not call install_tool for dirs without pyproject.toml."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create dir without pyproject.toml
        (src_dir / "empty_dir").mkdir()

        with patch.object(UvToolManager, "install_tool") as mock_install:
            UvToolManager.install_all(tmp_path)

        mock_install.assert_not_called()

    def test_handles_nonexistent_src_directory(self, mock_ensure_uv, mock_console, tmp_path):
        """Should handle missing src/ gracefully."""
        with patch.object(UvToolManager, "install_tool") as mock_install:
            UvToolManager.install_all(tmp_path)

        mock_install.assert_not_called()

    def test_defaults_to_cwd(self, mock_ensure_uv, mock_console, tmp_path, monkeypatch):
        """Should use cwd when no path arg."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        project = src_dir / "my_pkg"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]")

        monkeypatch.chdir(tmp_path)

        with patch.object(UvToolManager, "install_tool") as mock_install:
            UvToolManager.install_all()

        mock_install.assert_called_once()


class TestInstallTool:
    """Tests for UvToolManager.install_tool()."""

    def test_installs_tool_successfully(self, mock_console, mock_subprocess_run, tmp_path):
        """Should run uv tool install with correct args."""
        project = tmp_path / "my_pkg"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]")

        UvToolManager.install_tool(project)

        mock_subprocess_run.assert_called_once()
        call_args = mock_subprocess_run.call_args[0][0]
        assert call_args[:3] == ["uv", "tool", "install"]
        assert "--force" in call_args
        assert "--upgrade" in call_args
        assert str(project) in call_args
        mock_console.success.assert_called_once()

    def test_cleans_cache_and_retries_on_failure(self, mock_console, mock_subprocess_run, tmp_path):
        """Should clean cache and retry when install fails."""
        project = tmp_path / "my_pkg"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]")

        mock_subprocess_run.side_effect = [
            subprocess.CalledProcessError(1, "uv"),  # First install fails
            subprocess.CompletedProcess(args=[], returncode=0),  # Cache clean
            subprocess.CompletedProcess(args=[], returncode=0),  # Retry succeeds
        ]

        UvToolManager.install_tool(project)

        assert mock_subprocess_run.call_count == 3
        cache_clean_call = mock_subprocess_run.call_args_list[1][0][0]
        assert cache_clean_call[:3] == ["uv", "cache", "clean"]
        assert "my_pkg" in cache_clean_call
        mock_console.success.assert_called_once()

    def test_reports_failure_when_retry_fails(self, mock_console, mock_subprocess_run, tmp_path):
        """Should report failure when both attempts fail."""
        project = tmp_path / "my_pkg"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]")

        mock_subprocess_run.side_effect = [
            subprocess.CalledProcessError(1, "uv"),  # First fails
            subprocess.CompletedProcess(args=[], returncode=0),  # cache clean
            subprocess.CalledProcessError(1, "uv"),  # retry fails
        ]

        UvToolManager.install_tool(project)

        mock_console.failure.assert_called_once()
        mock_console.success.assert_not_called()


class TestRun:
    """Tests for UvToolManager.run()."""

    def test_runs_via_uv_tool_run(self, mock_ensure_uv, mock_subprocess_run, tmp_path):
        """Should use uv tool run in normal mode."""
        script = tmp_path / "bin" / "my-tool"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                UvToolManager.run(str(script), ["arg1", "arg2"])

        assert exc_info.value.code == 0
        call_args = mock_subprocess_run.call_args[0][0]
        assert call_args[:3] == ["uv", "tool", "run"]
        assert "my-tool" in call_args
        assert "arg1" in call_args
        assert "arg2" in call_args

    def test_uses_venv_in_dev_mode(self, mock_ensure_uv, mock_subprocess_run, tmp_path):
        """Should use venv python in dev mode when venv exists."""
        script = tmp_path / "bin" / "my-tool"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python")

        src_dir = tmp_path / "src" / "my_tool"
        src_dir.mkdir(parents=True)
        venv_bin = src_dir / ".venv" / "bin" / "my-tool"
        venv_bin.parent.mkdir(parents=True)
        venv_bin.write_text("#!/usr/bin/env python")

        with patch.dict(os.environ, {"BUVIS_DEV_MODE": "1"}):
            with pytest.raises(SystemExit) as exc_info:
                UvToolManager.run(str(script), ["arg1"])

        assert exc_info.value.code == 0
        call_args = mock_subprocess_run.call_args[0][0]
        assert str(venv_bin) == call_args[0]

    def test_uses_uv_run_project_in_dev_mode(self, mock_ensure_uv, mock_subprocess_run, tmp_path):
        """Should use uv run --project when no venv but project exists."""
        script = tmp_path / "bin" / "my-tool"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python")

        # Create project dir with pyproject.toml but NO venv
        src_dir = tmp_path / "src" / "my_tool"
        src_dir.mkdir(parents=True)
        (src_dir / "pyproject.toml").write_text("[project]")

        with patch.dict(os.environ, {"BUVIS_DEV_MODE": "1"}):
            with pytest.raises(SystemExit) as exc_info:
                UvToolManager.run(str(script), ["arg1"])

        assert exc_info.value.code == 0
        call_args = mock_subprocess_run.call_args[0][0]
        assert call_args[:3] == ["uv", "run", "--project"]
        assert str(src_dir) in call_args
        assert "-m" in call_args
        assert "my_tool" in call_args
        assert "arg1" in call_args

    def test_auto_installs_when_tool_not_found(self, mock_ensure_uv, mock_console, mock_subprocess_run, tmp_path):
        """Should auto-install and retry when tool not found."""
        script = tmp_path / "bin" / "my-tool"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python")

        project = tmp_path / "src" / "my_tool"
        project.mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]")

        mock_subprocess_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=1),
            subprocess.CompletedProcess(args=[], returncode=0),
            subprocess.CompletedProcess(args=[], returncode=0),
        ]

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                UvToolManager.run(str(script), [])

        assert exc_info.value.code == 0
        assert mock_subprocess_run.call_count == 3
        install_call = mock_subprocess_run.call_args_list[1][0][0]
        assert install_call[:3] == ["uv", "tool", "install"]

    def test_exits_with_error_when_no_project_in_dev_mode(self, mock_ensure_uv, tmp_path, capsys):
        """Should exit with error when no venv or project in dev mode."""
        script = tmp_path / "bin" / "my-tool"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python")

        with patch.dict(os.environ, {"BUVIS_DEV_MODE": "1"}):
            with pytest.raises(SystemExit) as exc_info:
                UvToolManager.run(str(script), [])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No venv or project found" in captured.err

    def test_exits_with_error_when_tool_not_found_and_no_source(
        self, mock_ensure_uv, mock_subprocess_run, tmp_path, capsys
    ):
        """Should exit with error when tool not found and no install source."""
        script = tmp_path / "bin" / "my-tool"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python")

        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=1)

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                UvToolManager.run(str(script), [])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_defaults_to_sys_argv(self, mock_ensure_uv, mock_subprocess_run, tmp_path):
        """Should use sys.argv[1:] when args is None."""
        script = tmp_path / "bin" / "my-tool"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python")

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, "argv", ["my-tool", "--help", "-v"]):
                with pytest.raises(SystemExit) as exc_info:
                    UvToolManager.run(str(script))

        assert exc_info.value.code == 0

        call_args = mock_subprocess_run.call_args[0][0]
        assert "--help" in call_args
        assert "-v" in call_args

    def test_exits_with_error_when_auto_install_retry_fails(
        self, mock_ensure_uv, mock_console, mock_subprocess_run, tmp_path
    ):
        """Should exit with non-zero when retry after auto-install fails."""
        script = tmp_path / "bin" / "my-tool"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python")

        project = tmp_path / "src" / "my_tool"
        project.mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]")

        mock_subprocess_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=1),
            subprocess.CompletedProcess(args=[], returncode=0),
            subprocess.CompletedProcess(args=[], returncode=1),
        ]

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                UvToolManager.run(str(script), [])

        assert exc_info.value.code == 1
        assert mock_subprocess_run.call_count == 3
