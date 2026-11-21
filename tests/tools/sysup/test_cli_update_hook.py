from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from click.testing import CliRunner


def test_sysup_cli_runs_with_the_update_check_stub_installed(runner: CliRunner) -> None:
    """The autouse stub must satisfy the real hook's call signature."""
    from sysup.cli import cli

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert not isinstance(result.exception, TypeError)
