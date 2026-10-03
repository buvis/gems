"""Critical scenarios from the PRD test strategy."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from click.testing import CliRunner
from klyreon.cli import cli

if TYPE_CHECKING:
    from collections.abc import Callable


class TestHelp:
    def test_help_exits_zero(self, runner: CliRunner) -> None:
        res = runner.invoke(cli, ["--help"])
        assert res.exit_code == 0
        for cmd in ("init", "new", "validate", "export-claims", "status"):
            assert cmd in res.output


class TestHappyPath:
    def test_init_new_three_validate_status(
        self,
        tmp_path: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
    ) -> None:
        root = tmp_path / "vault"
        klyreon_env(root)
        assert runner.invoke(cli, ["init", str(root)]).exit_code == 0
        for i in range(3):
            res = runner.invoke(cli, ["new", "--title", f"Note {i}"])
            assert res.exit_code == 0, res.output
        assert runner.invoke(cli, ["validate"]).exit_code == 0
        status = runner.invoke(cli, ["status"])
        assert status.exit_code == 0
        assert "zettels: 3" in status.output
