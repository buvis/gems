"""The five commands, driven through the Click CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from klyreon.cli import cli

if TYPE_CHECKING:
    from collections.abc import Callable


class TestInit:
    def test_init_then_validate_clean(
        self,
        tmp_path: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
    ) -> None:
        root = tmp_path / "vault"
        klyreon_env(root)
        res = runner.invoke(cli, ["init", str(root)])
        assert res.exit_code == 0, res.output
        for sub in ("sources", "wiki/notes", "wiki/mocs", "wiki/trails"):
            assert (root / sub).is_dir()
        assert (root / "voice.md").is_file()
        res_v = runner.invoke(cli, ["validate"])
        assert res_v.exit_code == 0, res_v.output

    def test_second_init_reports_existing_and_changes_no_mtime(
        self,
        tmp_path: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
    ) -> None:
        root = tmp_path / "vault"
        klyreon_env(root)
        runner.invoke(cli, ["init", str(root)])
        voice = root / "voice.md"
        before = voice.stat().st_mtime_ns
        res = runner.invoke(cli, ["init", str(root)])
        assert res.exit_code == 0
        assert "exists" in res.output
        assert voice.stat().st_mtime_ns == before, "idempotent init must not rewrite voice.md"

    def test_non_git_dir_warns_but_succeeds(
        self,
        tmp_path: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "vault"
        klyreon_env(root)
        # Force the "not a git work tree" branch deterministically. We cannot
        # rely on tmp_path being outside a git tree: CI runners place pytest's
        # basetemp under the checkout's git work tree (and /tmp is a symlink on
        # some runners, so GIT_CEILING_DIRECTORIES is not reliably honored), in
        # which case git's upward discovery reports the vault as inside a work
        # tree and the warning never fires. Stub the check at its import site.
        monkeypatch.setattr("klyreon.commands.init.is_git_vault", lambda _root: False)
        res = runner.invoke(cli, ["init", str(root)])
        assert res.exit_code == 0
        assert "not inside a git work tree" in res.output

    def test_init_never_runs_git_init(
        self,
        tmp_path: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Subprocess spy: fail loudly if 'git init' is ever shelled out.
        import subprocess

        real_run = subprocess.run

        def spy_run(args, *a, **k):  # type: ignore[no-untyped-def]
            if isinstance(args, (list, tuple)) and "init" in args and any("git" in str(x) for x in args):
                msg = f"init must never run 'git init', got argv: {args}"
                raise AssertionError(msg)
            return real_run(args, *a, **k)

        monkeypatch.setattr(subprocess, "run", spy_run)
        root = tmp_path / "vault"
        klyreon_env(root)
        res = runner.invoke(cli, ["init", str(root)])
        assert res.exit_code == 0


class TestNew:
    def test_new_concept_thesis_validates(
        self,
        tmp_path: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
    ) -> None:
        root = tmp_path / "vault"
        klyreon_env(root)
        runner.invoke(cli, ["init", str(root)])
        res = runner.invoke(cli, ["new", "--title", "A thesis", "--type", "note", "--concept-type", "thesis"])
        assert res.exit_code == 0, res.output
        created = list((root / "wiki" / "notes").glob("*.md"))
        assert len(created) == 1

    def test_new_utility_note(self, tmp_path: Path, runner: CliRunner, klyreon_env: Callable[[Path], None]) -> None:
        root = tmp_path / "vault"
        klyreon_env(root)
        runner.invoke(cli, ["init", str(root)])
        res = runner.invoke(cli, ["new", "--title", "Just a note"])
        assert res.exit_code == 0, res.output


class TestValidate:
    def test_exit_0_on_valid_corpus(
        self,
        copied_valid_vault: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
    ) -> None:
        klyreon_env(copied_valid_vault)
        res = runner.invoke(cli, ["validate"])
        assert res.exit_code == 0, res.output

    def test_exit_1_on_invalid(
        self,
        copied_valid_vault: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
    ) -> None:
        klyreon_env(copied_valid_vault)
        # Corrupt a zettel: publish: true is forbidden.
        target = copied_valid_vault / "wiki/notes/20260408180230.md"
        target.write_text(target.read_text().replace("type: snippet", "type: snippet\npublish: true"))
        res = runner.invoke(cli, ["validate"])
        assert res.exit_code == 1

    def test_json_output_parses(
        self,
        copied_valid_vault: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
    ) -> None:
        klyreon_env(copied_valid_vault)
        res = runner.invoke(cli, ["validate", "--json"])
        # The staleness notice goes to stderr; CliRunner may interleave it, so
        # parse from the first JSON brace.
        start = res.output.index("{")
        payload = json.loads(res.output[start:])
        assert payload["clean"] is True
        assert payload["error_count"] == 0


class TestStatus:
    def test_counts_match_corpus(
        self,
        copied_valid_vault: Path,
        runner: CliRunner,
        klyreon_env: Callable[[Path], None],
    ) -> None:
        klyreon_env(copied_valid_vault)
        res = runner.invoke(cli, ["status"])
        assert res.exit_code == 0, res.output
        assert "zettels: 2" in res.output  # one concept + one snippet in the corpus
