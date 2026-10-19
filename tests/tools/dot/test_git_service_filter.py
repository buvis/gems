from __future__ import annotations

import shlex
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dot.git.models import IndexEntry
from dot.git.service import DotGitService

ROOT = Path("/home/user/dotfiles")

FILTER_PREFIX = "filter.dot-host."

CLEAN_KEY = "filter.dot-host.clean"
SMUDGE_KEY = "filter.dot-host.smudge"
REQUIRED_KEY = "filter.dot-host.required"

CLEAN_VALUE = "BUVIS_AUTO_UPDATE=false dot filter clean -- %f"
SMUDGE_VALUE = "BUVIS_AUTO_UPDATE=false dot filter smudge -- %f"

UNSET = ("Command failed with exit code 1", "")
OK = ("", "")

NASTY_PATHS = [
    ".config/my notes/-settings.conf",
    ".config/o'brien's \"quoted\".cfg",
    "-leading-dash.toml",
]


def _config_parts(command: str) -> tuple[str, str, str | None] | None:
    """Classify a ``cfg config`` command string as (kind, key, value)."""
    tokens = shlex.split(command)
    if tokens[:2] != ["cfg", "config"]:
        return None
    rest = [token for token in tokens[2:] if token != "--get"]
    if not rest:
        return None
    if rest[0] == "--unset":
        return ("unset", rest[1], None)
    if len(rest) == 1:
        return ("read", rest[0], None)
    return ("write", rest[0], rest[1])


def _filter_config_calls(shell: MagicMock, kind: str) -> list[tuple[str, str | None]]:
    """List this feature's own ``filter.dot-host.*`` config calls, in order.

    Other keys are ignored on purpose: the constructor runs unrelated
    self-heals whose config writes are not this feature's behavior.
    """
    calls = []
    for call in shell.exe.call_args_list:
        parts = _config_parts(call.args[0])
        if parts is not None and parts[0] == kind and parts[1].startswith(FILTER_PREFIX):
            calls.append((parts[1], parts[2]))
    return calls


MUTATING_VERBS = {"checkout", "reset", "clean", "rm", "stash", "restore"}


def _verbs(shell: MagicMock) -> set[str]:
    """Collect the git verb of every command issued on the shell."""
    verbs = set()
    for call in shell.exe.call_args_list:
        tokens = shlex.split(call.args[0])
        if len(tokens) > 1:
            verbs.add(tokens[1])
    return verbs


def _responder(
    reads: dict[str, tuple[str, str]] | None = None,
    writes: dict[str, tuple[str, str]] | None = None,
):
    """Build a shell.exe side effect answering per config key."""
    read_results = reads or {}
    write_results = writes or {}

    def respond(command: str, cwd: Path) -> tuple[str, str]:
        parts = _config_parts(command)
        if parts is None:
            return OK
        kind, key, _ = parts
        if kind == "read":
            return read_results.get(key, UNSET)
        if kind == "write":
            return write_results.get(key, OK)
        return OK

    return respond


def _service(responder) -> tuple[DotGitService, MagicMock]:
    shell = MagicMock()
    shell.exe.side_effect = responder
    service = DotGitService(shell=shell, dotfiles_root=str(ROOT))
    return service, shell


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


@pytest.fixture
def git_service(shell: MagicMock) -> DotGitService:
    svc = DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")
    shell.exe.reset_mock()
    return svc


class TestFilterDriverSelfHeal:
    def test_writes_the_three_values_verbatim_when_clean_is_unset(self) -> None:
        _, shell = _service(_responder(reads={CLEAN_KEY: UNSET}))

        assert _filter_config_calls(shell, "write") == [
            (CLEAN_KEY, CLEAN_VALUE),
            (SMUDGE_KEY, SMUDGE_VALUE),
            (REQUIRED_KEY, "true"),
        ]
        assert _filter_config_calls(shell, "unset") == []

    def test_runs_every_self_heal_command_against_the_dotfiles_root(self) -> None:
        _, shell = _service(_responder(reads={CLEAN_KEY: UNSET}))

        assert {call.args[1] for call in shell.exe.call_args_list} == {ROOT}

    def test_writes_nothing_when_clean_is_already_set(self) -> None:
        _, shell = _service(_responder(reads={CLEAN_KEY: ("", "my own clean cmd\n")}))

        assert _filter_config_calls(shell, "write") == []
        assert _filter_config_calls(shell, "unset") == []
        assert (CLEAN_KEY, None) in _filter_config_calls(shell, "read")

    def test_treats_a_blank_clean_value_as_unset(self) -> None:
        _, shell = _service(_responder(reads={CLEAN_KEY: ("", "\n")}))

        assert [key for key, _ in _filter_config_calls(shell, "write")] == [CLEAN_KEY, SMUDGE_KEY, REQUIRED_KEY]
        assert _filter_config_calls(shell, "unset") == []

    def test_writes_all_three_when_only_smudge_is_already_set(self) -> None:
        _, shell = _service(
            _responder(reads={CLEAN_KEY: UNSET, SMUDGE_KEY: ("", "someone elses smudge\n")}),
        )

        assert _filter_config_calls(shell, "write") == [
            (CLEAN_KEY, CLEAN_VALUE),
            (SMUDGE_KEY, SMUDGE_VALUE),
            (REQUIRED_KEY, "true"),
        ]
        assert _filter_config_calls(shell, "unset") == []

    def test_self_heals_again_on_the_next_construction(self) -> None:
        _, shell = _service(_responder(reads={CLEAN_KEY: UNSET}))
        shell.exe.reset_mock()

        DotGitService(shell=shell, dotfiles_root=str(ROOT))

        assert _filter_config_calls(shell, "write") == [
            (CLEAN_KEY, CLEAN_VALUE),
            (SMUDGE_KEY, SMUDGE_VALUE),
            (REQUIRED_KEY, "true"),
        ]
        assert _filter_config_calls(shell, "unset") == []


class TestFilterDriverSelfHealRollback:
    def test_stops_before_smudge_and_required_when_the_clean_write_fails(self) -> None:
        _, shell = _service(
            _responder(reads={CLEAN_KEY: UNSET}, writes={CLEAN_KEY: ("error: could not lock config", "")}),
        )

        assert [key for key, _ in _filter_config_calls(shell, "write")] == [CLEAN_KEY]

    def test_unsets_clean_and_never_writes_required_when_the_smudge_write_fails(self) -> None:
        _, shell = _service(
            _responder(reads={CLEAN_KEY: UNSET}, writes={SMUDGE_KEY: ("error: could not lock config", "")}),
        )

        written = [key for key, _ in _filter_config_calls(shell, "write")]
        unset = [key for key, _ in _filter_config_calls(shell, "unset")]
        assert REQUIRED_KEY not in written
        assert CLEAN_KEY in unset
        assert not _verbs(shell) & MUTATING_VERBS

    def test_unsets_clean_and_smudge_when_the_required_write_fails(self) -> None:
        _, shell = _service(
            _responder(reads={CLEAN_KEY: UNSET}, writes={REQUIRED_KEY: ("error: could not lock config", "")}),
        )

        unset = [key for key, _ in _filter_config_calls(shell, "unset")]
        assert CLEAN_KEY in unset
        assert SMUDGE_KEY in unset
        assert not _verbs(shell) & MUTATING_VERBS

    def test_construction_survives_a_shell_that_fails_every_command(self) -> None:
        def always_fails(command: str, cwd: Path) -> tuple[str, str]:
            return ("fatal: not a git repository", "")

        service, shell = _service(always_fails)

        assert isinstance(service, DotGitService)
        assert not _verbs(shell) & MUTATING_VERBS


class TestFilterDriverConfigured:
    @pytest.mark.parametrize(
        "clean_value",
        ["BUVIS_AUTO_UPDATE=false dot filter clean -- %f", "my-own-clean --flag"],
    )
    def test_true_when_all_three_keys_are_set_with_required_true(self, clean_value: str) -> None:
        service, shell = _service(
            _responder(
                reads={
                    CLEAN_KEY: ("", clean_value + "\n"),
                    SMUDGE_KEY: ("", "any smudge\n"),
                    REQUIRED_KEY: ("", "true\n"),
                },
            ),
        )
        shell.exe.reset_mock()

        assert service.filter_driver_configured() is True

    @pytest.mark.parametrize("required", ["false", "1", "truex", "", "  "])
    def test_false_when_required_is_not_exactly_true(self, required: str) -> None:
        service, shell = _service(
            _responder(
                reads={
                    CLEAN_KEY: ("", "any clean\n"),
                    SMUDGE_KEY: ("", "any smudge\n"),
                    REQUIRED_KEY: ("", required + "\n"),
                },
            ),
        )
        shell.exe.reset_mock()

        assert service.filter_driver_configured() is False

    def test_false_when_required_is_unset(self) -> None:
        service, shell = _service(
            _responder(reads={CLEAN_KEY: ("", "any clean\n"), SMUDGE_KEY: ("", "any smudge\n")}),
        )
        shell.exe.reset_mock()

        assert service.filter_driver_configured() is False

    @pytest.mark.parametrize("blank", [CLEAN_KEY, SMUDGE_KEY])
    def test_false_when_clean_or_smudge_is_set_to_a_blank_value(self, blank: str) -> None:
        reads = {
            CLEAN_KEY: ("", "any clean\n"),
            SMUDGE_KEY: ("", "any smudge\n"),
            REQUIRED_KEY: ("", "true\n"),
        }
        reads[blank] = ("", "\n")
        service, shell = _service(_responder(reads=reads))
        shell.exe.reset_mock()

        assert service.filter_driver_configured() is False

    @pytest.mark.parametrize("missing", [CLEAN_KEY, SMUDGE_KEY])
    def test_false_when_clean_or_smudge_is_missing(self, missing: str) -> None:
        reads = {
            CLEAN_KEY: ("", "any clean\n"),
            SMUDGE_KEY: ("", "any smudge\n"),
            REQUIRED_KEY: ("", "true\n"),
        }
        reads[missing] = UNSET
        service, shell = _service(_responder(reads=reads))
        shell.exe.reset_mock()

        assert service.filter_driver_configured() is False

    def test_reads_all_three_keys_against_the_dotfiles_root(self) -> None:
        service, shell = _service(
            _responder(
                reads={
                    CLEAN_KEY: ("", "any clean\n"),
                    SMUDGE_KEY: ("", "any smudge\n"),
                    REQUIRED_KEY: ("", "true\n"),
                },
            ),
        )
        shell.exe.reset_mock()

        service.filter_driver_configured()

        assert {key for key, _ in _filter_config_calls(shell, "read")} == {CLEAN_KEY, SMUDGE_KEY, REQUIRED_KEY}
        assert {call.args[1] for call in shell.exe.call_args_list} == {ROOT}


class TestCheckAttrFilter:
    @pytest.mark.parametrize("value", ["dot-host", "dot-other"])
    def test_returns_the_effective_filter_value(self, git_service: DotGitService, shell: MagicMock, value: str) -> None:
        shell.exe.return_value = ("", f".bashrc\0filter\0{value}\0")

        assert git_service.check_attr_filter(".bashrc") == value

    def test_returns_none_when_git_reports_unspecified(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", ".bashrc\0filter\0unspecified\0")

        assert git_service.check_attr_filter(".bashrc") is None

    def test_returns_a_value_that_merely_starts_with_unspecified(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("", ".bashrc\0filter\0unspecified-dot-host\0")

        assert git_service.check_attr_filter(".bashrc") == "unspecified-dot-host"

    def test_reads_the_value_field_when_the_path_itself_names_an_attribute(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("", "dot-other.cfg\0filter\0dot-host\0")

        assert git_service.check_attr_filter("dot-other.cfg") == "dot-host"

    def test_reports_gits_unset_sentinel_as_the_effective_value(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("", ".bashrc\0filter\0unset\0")

        assert git_service.check_attr_filter(".bashrc") == "unset"

    def test_returns_none_when_git_fails_without_a_record(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("fatal: not a git repository", "")

        assert git_service.check_attr_filter(".bashrc") is None

    @pytest.mark.parametrize("path", NASTY_PATHS)
    def test_passes_a_quoted_pathname_and_never_a_literal_pathspec(
        self, git_service: DotGitService, shell: MagicMock, path: str
    ) -> None:
        shell.exe.return_value = ("", f"{path}\0filter\0dot-host\0")

        git_service.check_attr_filter(path)

        shell.exe.assert_called_once_with(f"cfg check-attr -z filter -- {shlex.quote(path)}", ROOT)


class TestRenormalize:
    @pytest.mark.parametrize("path", NASTY_PATHS)
    def test_stages_the_path_as_a_literal_pathspec_after_a_double_dash(
        self, git_service: DotGitService, shell: MagicMock, path: str
    ) -> None:
        git_service.renormalize(path)

        pathspec = shlex.quote(f":(literal){path}")
        shell.exe.assert_called_once_with(f"cfg add --renormalize -- {pathspec}", ROOT)

    def test_reports_success_without_output(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.renormalize(".bashrc")

        assert result.success is True
        assert result.output == ""

    def test_surfaces_git_stderr_as_failure(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("fatal: pathspec '.bashrc' did not match any files", "")

        result = git_service.renormalize(".bashrc")

        assert result.success is False
        assert result.error == "fatal: pathspec '.bashrc' did not match any files"


class TestIndexEntry:
    def test_holds_mode_and_sha_and_rejects_mutation(self) -> None:
        entry = IndexEntry(mode="120000", sha="0123456789abcdef0123456789abcdef01234567")

        assert (entry.mode, entry.sha) == ("120000", "0123456789abcdef0123456789abcdef01234567")
        with pytest.raises(FrozenInstanceError):
            setattr(entry, "mode", "100644")

    def test_distinguishes_entries_that_differ_only_by_mode(self) -> None:
        sha = "0123456789abcdef0123456789abcdef01234567"

        assert IndexEntry(mode="100644", sha=sha) != IndexEntry(mode="120000", sha=sha)


class TestCaptureIndexEntry:
    @pytest.mark.parametrize(
        ("mode", "sha"),
        [
            ("100644", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1"),
            ("120000", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb2"),
        ],
    )
    def test_parses_mode_and_sha_from_the_index_line(
        self, git_service: DotGitService, shell: MagicMock, mode: str, sha: str
    ) -> None:
        shell.exe.return_value = ("", f"{mode} {sha} 0\t.bashrc\n")

        entry = git_service.capture_index_entry(".bashrc")

        assert entry is not None
        assert (entry.mode, entry.sha) == (mode, sha)
        pathspec = shlex.quote(":(literal).bashrc")
        shell.exe.assert_called_once_with(f"cfg ls-files -s -- {pathspec}", ROOT)

    def test_ignores_stage_and_path_fields_that_look_like_mode_and_sha(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        path = "my dir/100755 ddddddd4.txt"
        sha = "ccccccccccccccccccccccccccccccccccccccc3"
        shell.exe.return_value = ("", f"100644 {sha} 0\t{path}\n")

        entry = git_service.capture_index_entry(path)

        assert entry is not None
        assert (entry.mode, entry.sha) == ("100644", sha)
        shell.exe.assert_called_once_with(f"cfg ls-files -s -- {shlex.quote(f':(literal){path}')}", ROOT)

    def test_refuses_to_capture_a_conflicted_path_with_no_stage_zero_record(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        base = "ddddddddddddddddddddddddddddddddddddddd4"
        ours = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee5"
        theirs = "fffffffffffffffffffffffffffffffffffffff6"
        shell.exe.return_value = (
            "",
            f"100644 {base} 1\t.bashrc\n100644 {ours} 2\t.bashrc\n100644 {theirs} 3\t.bashrc\n",
        )

        assert git_service.capture_index_entry(".bashrc") is None

    def test_returns_none_when_the_path_has_no_index_entry(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        assert git_service.capture_index_entry(".bashrc") is None

    def test_returns_none_when_git_fails(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("fatal: not a git repository", "")

        assert git_service.capture_index_entry(".bashrc") is None

    @pytest.mark.parametrize("path", NASTY_PATHS)
    def test_queries_a_literal_pathspec_against_the_dotfiles_root(
        self, git_service: DotGitService, shell: MagicMock, path: str
    ) -> None:
        shell.exe.return_value = ("", "")

        git_service.capture_index_entry(path)

        pathspec = shlex.quote(f":(literal){path}")
        shell.exe.assert_called_once_with(f"cfg ls-files -s -- {pathspec}", ROOT)


class TestRestoreIndexEntry:
    @pytest.mark.parametrize(
        ("mode", "sha"),
        [
            ("100644", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1"),
            ("120000", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb2"),
        ],
    )
    def test_restores_the_captured_mode_and_sha_with_one_cacheinfo_call(
        self, git_service: DotGitService, shell: MagicMock, mode: str, sha: str
    ) -> None:
        git_service.restore_index_entry(".bashrc", IndexEntry(mode=mode, sha=sha))

        shell.exe.assert_called_once()
        command, cwd = shell.exe.call_args.args
        assert shlex.split(command) == ["cfg", "update-index", "--add", "--cacheinfo", f"{mode},{sha},.bashrc"]
        assert cwd == ROOT

    @pytest.mark.parametrize("path", NASTY_PATHS)
    def test_keeps_a_cacheinfo_path_shell_safe(self, git_service: DotGitService, shell: MagicMock, path: str) -> None:
        sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1"

        git_service.restore_index_entry(path, IndexEntry(mode="100644", sha=sha))

        shell.exe.assert_called_once()
        command = shell.exe.call_args.args[0]
        assert shlex.split(command)[-1] == f"100644,{sha},{path}"

    @pytest.mark.parametrize("path", NASTY_PATHS)
    def test_drops_the_index_entry_when_there_was_none_before(
        self, git_service: DotGitService, shell: MagicMock, path: str
    ) -> None:
        git_service.restore_index_entry(path, None)

        pathspec = shlex.quote(f":(literal){path}")
        shell.exe.assert_called_once_with(f"cfg rm --cached --ignore-unmatch -- {pathspec}", ROOT)

    def test_reports_success_for_a_restored_entry(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")
        entry = IndexEntry(mode="100644", sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1")

        assert git_service.restore_index_entry(".bashrc", entry).success is True

    @pytest.mark.parametrize(
        "entry",
        [None, IndexEntry(mode="100644", sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1")],
    )
    def test_surfaces_git_stderr_as_failure(
        self, git_service: DotGitService, shell: MagicMock, entry: IndexEntry | None
    ) -> None:
        shell.exe.return_value = ("fatal: Unable to mark file .bashrc", "")

        result = git_service.restore_index_entry(".bashrc", entry)

        assert result.success is False
        assert result.error == "fatal: Unable to mark file .bashrc"
