from __future__ import annotations

from types import SimpleNamespace

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from fren.cli import cli


class TestSlugExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path):
        target = tmp_path / "file.txt"
        target.write_text("x")
        fake_result = CommandResult(success=False, error="slug failed")
        mocker.patch(
            "fren.commands.slug.slug.CommandSlug",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["slug", str(target)])

        assert result.exit_code != 0
        assert "slug failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path):
        target = tmp_path / "file.txt"
        target.write_text("x")
        fake_result = CommandResult(success=True, output="renamed")
        mocker.patch(
            "fren.commands.slug.slug.CommandSlug",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["slug", str(target)])

        assert result.exit_code == 0


class TestDirectorizeExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path):
        directory = tmp_path / "dir"
        directory.mkdir()
        fake_result = CommandResult(success=False, error="directorize failed")
        mocker.patch(
            "fren.commands.directorize.directorize.CommandDirectorize",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["directorize", str(directory)])

        assert result.exit_code != 0
        assert "directorize failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path):
        directory = tmp_path / "dir"
        directory.mkdir()
        fake_result = CommandResult(success=True, output="wrapped")
        mocker.patch(
            "fren.commands.directorize.directorize.CommandDirectorize",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["directorize", str(directory)])

        assert result.exit_code == 0


class TestFlattenExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        destination = tmp_path / "dest"
        fake_result = CommandResult(success=False, error="flatten failed")
        mocker.patch(
            "fren.commands.flatten.flatten.CommandFlatten",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["flatten", str(source), str(destination)])

        assert result.exit_code != 0
        assert "flatten failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        destination = tmp_path / "dest"
        fake_result = CommandResult(success=True, output="flattened")
        mocker.patch(
            "fren.commands.flatten.flatten.CommandFlatten",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["flatten", str(source), str(destination)])

        assert result.exit_code == 0


class TestNormalizeExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path):
        directory = tmp_path / "dir"
        directory.mkdir()
        fake_result = CommandResult(success=False, error="normalize failed")
        mocker.patch(
            "fren.commands.normalize.normalize.CommandNormalize",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["normalize", str(directory)])

        assert result.exit_code != 0
        assert "normalize failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path):
        directory = tmp_path / "dir"
        directory.mkdir()
        fake_result = CommandResult(success=True, output="normalized")
        mocker.patch(
            "fren.commands.normalize.normalize.CommandNormalize",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["normalize", str(directory)])

        assert result.exit_code == 0
