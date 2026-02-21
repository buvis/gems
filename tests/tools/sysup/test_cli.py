from __future__ import annotations

import click

from sysup.cli import cli


class TestCli:
    def test_cli_group_exists(self) -> None:
        assert isinstance(cli, click.Group)

    def test_mac_command_exists(self) -> None:
        assert "mac" in cli.commands

    def test_pip_command_exists(self) -> None:
        assert "pip" in cli.commands

    def test_wsl_command_exists(self) -> None:
        assert "wsl" in cli.commands
