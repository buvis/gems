"""Divergence save inside DotGitService.pull, with a mocked shell and git subprocess."""

from __future__ import annotations

import socket
import subprocess
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from buvis.pybase.filesystem import atomic_write_bytes
from dot.divergence import divergence_dir
from dot.git.service import DotGitService

FETCH = "cfg fetch"
UPSTREAM = "cfg rev-parse --verify --quiet @{u}"
HIDE = "cfg secret hide -m -F"
INCOMING = "cfg diff --name-only --no-renames -z HEAD...@{u}"
STAGED = "cfg diff --cached --name-only --no-renames --ignore-submodules=all -z"
UNSTAGED = "cfg diff --name-only --no-renames --ignore-submodules=all -z"
STAGED_DELETED = "cfg diff --cached --name-only --no-renames --diff-filter=D -z"
HEAD = "cfg rev-parse HEAD"
UPSTREAM_ID = "cfg rev-parse @{u}"
PULL = "cfg pull"
SUB_RESET = "cfg submodule foreach git reset --hard"
SUB_INIT = "cfg submodule update --init"
SUB_UPDATE = "cfg submodule update --remote --merge"
REVEAL = "cfg secret reveal -f"
BASE_ID = "a" * 40
UP_ID = "b" * 40
DIFF_BODY = b"diff --git a/x b/x\nindex 1..2\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\r\n+new\x00\r\n"
STAMP = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)


def _restore(path: str) -> str:
    return f"cfg --literal-pathspecs restore --source=HEAD --staged --worktree -- {path}"


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return STAMP


class Harness:
    """A DotGitService wired to a scripted shell, git subprocess and writer."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch, responses: dict[str, tuple[str, str]]) -> None:
        self.root = root
        self.responses = responses
        self.events: list[tuple[str, object]] = []
        self.shell = MagicMock()
        self.shell.is_command_available.return_value = False
        self.shell.exe.side_effect = self._exe
        self.service = DotGitService(self.shell, str(root))
        self.events.clear()
        self.run = MagicMock(side_effect=self._run)
        self.diff_result = subprocess.CompletedProcess([], 0, DIFF_BODY, b"")
        self.written: list[tuple[Path, bytes]] = []
        monkeypatch.setattr("dot.git.service.subprocess.run", self.run)
        monkeypatch.setattr("dot.git.service.atomic_write_bytes", self._write)
        monkeypatch.setattr("dot.git.service.datetime", _FixedDatetime)

    def _exe(self, cmd: str, _wd: Path) -> tuple[str, str]:
        self.events.append(("exe", cmd))
        return self.responses.get(cmd, ("", ""))

    def _run(self, argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.events.append(("run", argv))
        return self.diff_result

    def _write(self, path: Path, data: bytes) -> None:
        self.events.append(("write", path))
        self.written.append((path, data))
        atomic_write_bytes(path, data)

    @property
    def commands(self) -> list[str]:
        return [str(e[1]) for e in self.events if e[0] == "exe"]

    @property
    def restores(self) -> list[str]:
        return [c for c in self.commands if "restore" in c]


def _responses(incoming: str = "", staged: str = "", unstaged: str = "") -> dict[str, tuple[str, str]]:
    return {
        INCOMING: ("", incoming),
        STAGED: ("", staged),
        UNSTAGED: ("", unstaged),
        HEAD: ("", BASE_ID + "\n"),
        UPSTREAM_ID: ("", UP_ID + "\n"),
    }


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "home"
    r.mkdir()
    return r


def _patch_path(root: Path) -> Path:
    return divergence_dir(root) / "20261016T120000Z.patch"


class TestNoDivergence:
    def test_no_upstream_runs_no_diff_and_plain_pull(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, {UPSTREAM: ("no upstream", "")})

        result = h.service.pull(fetched=True)

        assert result.success
        assert result.warnings == []
        assert h.commands == [UPSTREAM, PULL, SUB_RESET, SUB_INIT, SUB_UPDATE]
        h.run.assert_not_called()

    def test_nothing_selected_writes_no_patch_and_resets_nothing(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="a\0", unstaged="b\0", staged="c\0"))

        result = h.service.pull(fetched=True)

        assert result.success
        assert result.output == "Dotfiles pulled successfully"
        assert result.warnings == []
        assert h.restores == []
        h.run.assert_not_called()
        assert not divergence_dir(root).exists()

    def test_default_pull_fetches_then_checks_divergence_then_pulls(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        h = Harness(root, monkeypatch, _responses())

        result = h.service.pull()

        assert result.success
        assert h.commands == [
            FETCH,
            UPSTREAM,
            INCOMING,
            STAGED,
            UNSTAGED,
            STAGED_DELETED,
            PULL,
            SUB_RESET,
            SUB_INIT,
            SUB_UPDATE,
        ]

    def test_fetch_failure_stops_before_anything_else(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, {FETCH: ("unreachable", "")})

        result = h.service.pull()

        assert not result.success
        assert result.error == "Fetch failed: unreachable"
        assert h.commands == [FETCH]


class TestDivergenceSave:
    def test_patch_is_written_before_first_restore(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="y\0x\0q\0", unstaged="x\0z\0", staged="y\0"))

        result = h.service.pull(fetched=True)

        assert result.success
        kinds = [e[0] for e in h.events]
        first_restore = next(i for i, e in enumerate(h.events) if e[0] == "exe" and "restore" in str(e[1]))
        assert kinds.index("run") < kinds.index("write") < first_restore

    def test_binary_capture_runs_at_root_with_exact_argv(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="x\0y\0", unstaged="x\0", staged="y\0"))

        h.service.pull(fetched=True)

        h.run.assert_called_once_with(
            [
                "git",
                f"--git-dir={root}/.buvis",
                f"--work-tree={root}",
                "--literal-pathspecs",
                "diff",
                "--binary",
                "--full-index",
                "--no-renames",
                "--no-ext-diff",
                "--no-textconv",
                "--no-color",
                "--src-prefix=a/",
                "--dst-prefix=b/",
                "HEAD",
                "--",
                "x",
                "y",
            ],
            cwd=root,
            capture_output=True,
            text=False,
            check=False,
        )

    def test_raw_diff_bytes_follow_the_header_unchanged(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="x\0", unstaged="x\0"))

        result = h.service.pull(fetched=True)

        header = (
            f"# dot divergence patch\n# base: {BASE_ID}\n# upstream: {UP_ID}\n# host: {socket.gethostname()}\n\n"
        ).encode()
        assert h.written == [(_patch_path(root), header + DIFF_BODY)]
        assert _patch_path(root).read_bytes() == header + DIFF_BODY
        assert divergence_dir(root).stat().st_mode & 0o777 == 0o700
        assert result.warnings[0] == f"divergence patch saved: {_patch_path(root)}"

    def test_saved_paths_equal_reset_paths(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="b\0a\0c\0", unstaged="c\0a\0", staged="b\0"))

        result = h.service.pull(fetched=True)

        argv = h.run.call_args.args[0]
        saved = argv[argv.index("--") + 1 :]
        assert saved == ["a", "b", "c"]
        assert h.restores == [_restore(p) for p in saved]
        assert result.warnings == [
            f"divergence patch saved: {_patch_path(root)}",
            "reset to HEAD, local edit in patch: a",
            "reset to HEAD, local edit in patch: b",
            "reset to HEAD, local edit in patch: c",
        ]

    def test_path_with_spaces_is_quoted_for_restore(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="my file\0", unstaged="my file\0"))

        h.service.pull(fetched=True)

        assert h.restores == [_restore("'my file'")]
        assert h.run.call_args.args[0][-1] == "my file"

    def test_excluded_path_and_paths_under_excluded_dir_are_skipped(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dirty = "t\0d/f\0dx\0x\0"
        h = Harness(root, monkeypatch, _responses(incoming=dirty, unstaged=dirty))

        h.service.pull(exclude=["t", "d"], fetched=True)

        assert h.run.call_args.args[0][-2:] == ["dx", "x"]
        assert h.restores == [_restore("dx"), _restore("x")]


class TestDivergenceAbortsBeforeReset:
    def test_mixed_staged_and_unstaged_path_stops_pull(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="x\0y\0z\0", staged="x\0z\0", unstaged="x\0y\0z\0"))

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == "pull stopped: x, z have both staged and unstaged changes; commit or unstage them first"
        assert h.restores == []
        assert PULL not in h.commands
        h.run.assert_not_called()

    def test_untracked_path_kept_on_disk_stops_pull(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        responses = _responses(incoming="x\0g\0", staged="x\0g\0")
        responses[STAGED_DELETED] = ("", "x\0g\0")
        (root / "x").write_bytes(b"kept after git rm --cached")
        h = Harness(root, monkeypatch, responses)

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == "pull stopped: x untracked but kept on disk; commit the removal or re-add first"
        assert h.restores == []
        h.run.assert_not_called()

    def test_deleted_path_gone_from_disk_is_saved(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        responses = _responses(incoming="g\0", staged="g\0")
        responses[STAGED_DELETED] = ("", "g\0")
        h = Harness(root, monkeypatch, responses)

        result = h.service.pull(fetched=True)

        assert result.success
        assert h.restores == [_restore("g")]

    @pytest.mark.parametrize("failing", [INCOMING, STAGED, UNSTAGED, STAGED_DELETED])
    def test_detection_error_stops_pull(self, root: Path, monkeypatch: pytest.MonkeyPatch, failing: str) -> None:
        responses = _responses(incoming="x\0", unstaged="x\0")
        responses[failing] = ("bad revision", "")
        h = Harness(root, monkeypatch, responses)

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == "divergence check failed: bad revision"
        assert h.restores == []
        assert PULL not in h.commands

    def test_read_only_divergence_dir_stops_pull(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="x\0", unstaged="x\0"))
        d = divergence_dir(root)
        d.mkdir(parents=True)
        d.chmod(0o555)
        try:
            result = h.service.pull(fetched=True)
        finally:
            d.chmod(0o755)

        assert not result.success
        assert result.error is not None
        assert result.error.startswith("could not save divergence patch: ")
        assert h.restores == []
        assert PULL not in h.commands

    def test_existing_patch_name_stops_pull(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="x\0", unstaged="x\0"))
        _patch_path(root).parent.mkdir(parents=True)
        _patch_path(root).write_bytes(b"earlier")

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == f"could not save divergence patch: {_patch_path(root)} already exists"
        assert _patch_path(root).read_bytes() == b"earlier"
        assert h.restores == []

    @pytest.mark.parametrize("failing", [HEAD, UPSTREAM_ID])
    def test_metadata_failure_stops_pull(self, root: Path, monkeypatch: pytest.MonkeyPatch, failing: str) -> None:
        responses = _responses(incoming="x\0", unstaged="x\0")
        responses[failing] = ("fatal: no", "")
        h = Harness(root, monkeypatch, responses)

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error is not None
        assert result.error.startswith("could not save divergence patch: ")
        assert h.written == []
        assert h.restores == []

    def test_failing_git_diff_stops_pull(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, _responses(incoming="x\0", unstaged="x\0"))
        h.diff_result = subprocess.CompletedProcess([], 128, b"", b"fatal: bad object\n")

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == "could not save divergence patch: fatal: bad object"
        assert h.written == []
        assert h.restores == []


class TestFailuresAfterSaveKeepWarnings:
    def test_second_restore_failure_reports_patch_and_first_reset(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        responses = _responses(incoming="x\0y\0z\0", unstaged="x\0y\0z\0")
        responses[_restore("y")] = ("permission denied", "")
        h = Harness(root, monkeypatch, responses)

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == "reset failed for y: permission denied"
        assert result.warnings == [
            f"divergence patch saved: {_patch_path(root)}",
            "reset to HEAD, local edit in patch: x",
        ]
        assert PULL not in h.commands

    @pytest.mark.parametrize(
        ("failing", "error"),
        [
            (PULL, "boom"),
            (SUB_RESET, "Submodule reset failed: boom"),
            (SUB_INIT, "Submodule init failed: boom"),
            (SUB_UPDATE, "Submodule update failed: boom"),
            (REVEAL, "Secret reveal failed: boom"),
        ],
    )
    def test_later_failure_keeps_patch_and_all_reset_warnings(
        self, root: Path, monkeypatch: pytest.MonkeyPatch, failing: str, error: str
    ) -> None:
        responses = _responses(incoming="x\0y\0", unstaged="x\0y\0")
        responses[failing] = ("boom", "")
        h = Harness(root, monkeypatch, responses)
        h.shell.is_command_available.return_value = True

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == error
        assert result.warnings == [
            f"divergence patch saved: {_patch_path(root)}",
            "reset to HEAD, local edit in patch: x",
            "reset to HEAD, local edit in patch: y",
        ]


SECRET_DIRTY = ".gitsecret/paths/mapping.cfg\0x.secret\0"
SECRET_HINT = (
    "secret x saved encrypted in patch; "
    "to read it, git apply the patch at its base commit and run git secret reveal there"
)


class TestSecretHide:
    def test_hide_runs_after_upstream_check_and_before_selection(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        h = Harness(root, monkeypatch, _responses())
        h.shell.is_command_available.return_value = True

        result = h.service.pull(fetched=True)

        assert result.success
        assert h.commands == [
            UPSTREAM,
            HIDE,
            INCOMING,
            STAGED,
            UNSTAGED,
            STAGED_DELETED,
            PULL,
            SUB_RESET,
            SUB_INIT,
            SUB_UPDATE,
            REVEAL,
        ]

    def test_hide_failure_stops_before_any_diff_save_reset_or_pull(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        responses = _responses(incoming="x.secret\0", unstaged="x.secret\0")
        responses[HIDE] = ("gpg: no public key", "")
        h = Harness(root, monkeypatch, responses)
        h.shell.is_command_available.return_value = True

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == "secret hide failed: gpg: no public key"
        assert h.commands == [UPSTREAM, HIDE]
        h.run.assert_not_called()
        assert h.written == []

    def test_no_upstream_skips_hide(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        h = Harness(root, monkeypatch, {UPSTREAM: ("no upstream", "")})
        h.shell.is_command_available.return_value = True

        result = h.service.pull(fetched=True)

        assert result.success
        assert h.commands == [UPSTREAM, PULL, SUB_RESET, SUB_INIT, SUB_UPDATE, REVEAL]

    def test_reset_secret_gets_recovery_hint_and_mapping_does_not(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        h = Harness(root, monkeypatch, _responses(incoming=SECRET_DIRTY, unstaged=SECRET_DIRTY))
        h.shell.is_command_available.return_value = True

        result = h.service.pull(fetched=True)

        assert result.success
        assert result.warnings == [
            f"divergence patch saved: {_patch_path(root)}",
            "reset to HEAD, local edit in patch: .gitsecret/paths/mapping.cfg",
            "reset to HEAD, local edit in patch: x.secret",
            SECRET_HINT,
        ]

    def test_failed_secret_reset_gets_no_hint(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        responses = _responses(incoming=SECRET_DIRTY, unstaged=SECRET_DIRTY)
        responses[_restore("x.secret")] = ("denied", "")
        h = Harness(root, monkeypatch, responses)
        h.shell.is_command_available.return_value = True

        result = h.service.pull(fetched=True)

        assert not result.success
        assert result.error == "reset failed for x.secret: denied"
        assert result.warnings == [
            f"divergence patch saved: {_patch_path(root)}",
            "reset to HEAD, local edit in patch: .gitsecret/paths/mapping.cfg",
        ]
