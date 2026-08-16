from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult
from dot.cli import _dotfiles_root, cli


class TestDotfilesRootHelper:
    def test_returns_env_var_when_set(self, monkeypatch) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", "/custom/dotfiles/root")
        assert _dotfiles_root() == "/custom/dotfiles/root"

    def test_falls_back_to_home_when_unset(self, monkeypatch, mocker) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        mocker.patch("dot.cli.Path.home", return_value=Path("/fake/home"))
        assert _dotfiles_root() == "/fake/home"


class TestDotfilesRootPropagation:
    DOTFILES_ROOT = "/fake/dotfiles/root"

    def test_status_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.status.status.CommandStatus")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="All clean")
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT

    def test_add_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.add.add.CommandAdd")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Added")
        result = runner.invoke(cli, ["add", "/tmp/test.txt"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT

    def test_encrypt_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.encrypt.encrypt.CommandEncrypt")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Registered")
        result = runner.invoke(cli, ["encrypt", "secret.txt"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT

    def test_rm_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.rm.rm.CommandRm")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Removed")
        result = runner.invoke(cli, ["rm", ".bashrc"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT

    def test_delete_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.delete.delete.CommandDelete")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Deleted")
        result = runner.invoke(cli, ["delete", ".bashrc"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT

    def test_pull_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.pull.pull.CommandPull")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Dotfiles pulled successfully"
        )
        result = runner.invoke(cli, ["pull"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT

    def test_commit_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.commit.commit.CommandCommit")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Changes committed")
        result = runner.invoke(cli, ["commit", "test msg"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT

    def test_unstage_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.unstage.unstage.CommandUnstage")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="All files unstaged")
        result = runner.invoke(cli, ["unstage"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT

    def test_push_passes_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", self.DOTFILES_ROOT)
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.push.push.CommandPush")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Changes pushed")
        result = runner.invoke(cli, ["push"])
        assert result.exit_code == 0
        assert mock_cmd_cls.call_args.kwargs["dotfiles_root"] == self.DOTFILES_ROOT


class TestRunCommandStaysOutOfScope:
    def test_run_does_not_pass_dotfiles_root(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", "/fake/dotfiles/root")
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.run.run.CommandRun")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="ok")
        result = runner.invoke(cli, ["run", "status"])
        assert result.exit_code == 0
        assert "dotfiles_root" not in mock_cmd_cls.call_args.kwargs
