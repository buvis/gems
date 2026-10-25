"""Real-git tests for the shared ``dot-host`` filter.

Every test drives real ``git`` processes against temporary bare repositories and
asserts the bytes that land in the index and in the work-tree, never an exit code
alone. Git config, ``HOME`` and ``PATH`` are isolated per test, so the user's own
dotfiles repository is never read or written.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter
from buvis.pybase.result import CommandResult
from dot.commands.localize.share import CommandShare
from dot.commands.setup.setup import CommandSetup
from dot.divergence import divergence_dir
from dot.git.filter_driver import (
    FILTER_CLEAN_KEY,
    FILTER_CLEAN_VALUE,
    FILTER_SMUDGE_KEY,
    FILTER_SMUDGE_VALUE,
)
from dot.git.service import DotGitService

from tests.tools.dot.conftest import _disable_git_secret

pytestmark = pytest.mark.skipif(os.name == "nt", reason="the filter driver runs through a POSIX shell")

TOKEN = b"@HOME@"


def _run(
    argv: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    """Run a fixed git argv (no shell) and return the completed process with raw bytes."""
    return subprocess.run(  # fixed git argv, no shell, test-only
        argv, cwd=cwd, env=env, capture_output=True, check=check
    )


def _git(home: Path) -> list[str]:
    """Return the base argv for a bare dotfiles git invocation on a host."""
    return ["git", f"--git-dir={home}/.buvis", f"--work-tree={home}"]


def _index_bytes(home: Path, rel: str) -> bytes:
    """Return the stage-zero blob bytes of a tracked path."""
    return _run([*_git(home), "cat-file", "-p", f":{rel}"], cwd=home).stdout


def _status(home: Path) -> str:
    """Return the porcelain status of a host work-tree."""
    return _run([*_git(home), "status", "--porcelain"], cwd=home).stdout.decode()


def _head(home: Path) -> str:
    """Return the commit id a host's HEAD points at."""
    return _run([*_git(home), "rev-parse", "HEAD"], cwd=home).stdout.decode().strip()


def _fs(path: Path) -> bytes:
    """Return the filesystem bytes of a path."""
    return os.fsencode(str(path))


def _home_line(home: Path) -> bytes:
    """Return a config line carrying the host's own home path."""
    return b"export TOOLS=" + _fs(home) + b"/bin\n"


def _token_line() -> bytes:
    """Return the tokenized form of :func:`_home_line`."""
    return b"export TOOLS=" + TOKEN + b"/bin\n"


def _track(home: Path, rel: str, data: bytes) -> None:
    """Write a file under a host home and stage it."""
    target = home / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    _run([*_git(home), "add", "--", rel], cwd=home)


def _commit(home: Path, message: str) -> None:
    """Commit whatever is staged on a host."""
    _run([*_git(home), "commit", "-qm", message], cwd=home)


def _push(home: Path) -> None:
    """Push a host's master branch to origin."""
    _run([*_git(home), "push", "-q", "origin", "master"], cwd=home)


def _share(home: Path, rel: str) -> CommandResult:
    """Run ``dot localize --shared`` for a path on a host."""
    return CommandShare(ShellAdapter(suppress_logging=True), str(home), rel).execute()


def _share_commit(home: Path, rel: str, data: bytes) -> None:
    """Track, share and commit a home-bearing file on a host."""
    _track(home, rel, data)
    _commit(home, f"track {rel}")
    result = _share(home, rel)
    assert result.success, result.error
    _commit(home, f"share {rel}")


def _setup_host(origin: Path, home: Path) -> Path:
    """Clone origin onto a fresh host home through ``dot setup``."""
    home.mkdir(parents=True, exist_ok=True)
    result = CommandSetup(ShellAdapter(suppress_logging=True), str(home), str(origin)).execute()
    assert result.success, result.error
    return home


def _pull(home: Path) -> CommandResult:
    """Pull on a host with git-secret reported as unavailable."""
    shell = ShellAdapter(suppress_logging=True)
    _disable_git_secret(shell)
    return DotGitService(shell, str(home)).pull()


def _patches(home: Path) -> list[Path]:
    """Return the divergence patches saved on a host."""
    d = divergence_dir(home)
    return sorted(d.glob("*.patch")) if d.is_dir() else []


def _apply_at(origin: Path, base: str, patch: Path, dest: Path) -> Path:
    """Clone origin at ``base`` with the filter configured and apply a patch there."""
    _run(["git", "clone", "-q", "--no-checkout", str(origin), str(dest)])
    git = ["git", f"--git-dir={dest}/.git", f"--work-tree={dest}"]
    _run([*git, "config", FILTER_CLEAN_KEY, FILTER_CLEAN_VALUE], cwd=dest)
    _run([*git, "config", FILTER_SMUDGE_KEY, FILTER_SMUDGE_VALUE], cwd=dest)
    _run([*git, "checkout", "-q", base], cwd=dest)
    _run([*git, "apply", str(patch)], cwd=dest)
    return dest


class _RecordingShell(ShellAdapter):
    """A shell adapter that records every command it runs, in order."""

    def __init__(self) -> None:
        super().__init__(suppress_logging=True)
        self.commands: list[str] = []

    def exe(self, command: str, working_dir: Path | None) -> tuple[str, str]:
        self.commands.append(command)
        return super().exe(command, working_dir)


@pytest.fixture
def git_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate git config, HOME and PATH; return the resolved temp root.

    The root is resolved because git runs the filter with the work-tree's real
    path as its working directory, which is what the filter turns into a token.
    """
    root = Path(os.path.realpath(tmp_path))
    fake_home = root / "git-home"
    fake_home.mkdir()
    config = fake_home / "gitconfig"
    config.write_text(
        "[user]\n\tname = Test User\n\temail = test@test.local\n"
        "[commit]\n\tgpgsign = false\n"
        "[core]\n\tautocrlf = false\n"
    )
    # Never the user's own config, home or dotfiles repository.
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "DOTFILES_ROOT", "BUVIS_CONFIG_DIR", "BUVIS_CONFIG_FILE"):
        monkeypatch.delenv(var, raising=False)
    for var in ("GIT_AUTHOR", "GIT_COMMITTER"):
        monkeypatch.setenv(f"{var}_NAME", "Test User")
        monkeypatch.setenv(f"{var}_EMAIL", "test@test.local")
    monkeypatch.setenv("BUVIS_AUTO_UPDATE", "false")
    # Not resolved: the venv bin/python is a symlink and resolving leaves the venv.
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    assert shutil.which("dot"), "dot entry point missing from the venv bin; run uv sync"
    return root


@pytest.fixture
def origin(git_sandbox: Path) -> Path:
    """Create a bare origin seeded with a .gitignore commit on master."""
    origin = git_sandbox / "origin.git"
    _run(["git", "init", "-q", "--bare", "-b", "master", str(origin)])
    seed = git_sandbox / "seed"
    _run(["git", "clone", "-q", str(origin), str(seed)])
    (seed / ".gitignore").write_text(".buvis\n")
    _run(["git", "add", ".gitignore"], cwd=seed)
    _run(["git", "commit", "-qm", "init"], cwd=seed)
    _run(["git", "push", "-q", "origin", "master"], cwd=seed)
    return origin


@pytest.fixture
def host_a(git_sandbox: Path, origin: Path) -> Path:
    """Set up the first host from origin."""
    return _setup_host(origin, git_sandbox / "host-a")


class TestIndexHoldsTokens:
    def test_shared_file_is_tokenized_in_the_index_and_host_valued_on_disk(self, host_a: Path) -> None:
        _track(host_a, ".zshrc", _home_line(host_a))
        _commit(host_a, "track .zshrc")

        result = _share(host_a, ".zshrc")

        assert result.success, result.error
        assert result.output == "shared .zshrc: 1 host value(s) replaced"
        _commit(host_a, "share .zshrc")
        assert _index_bytes(host_a, ".zshrc") == _token_line()
        assert (host_a / ".zshrc").read_bytes() == _home_line(host_a)
        assert _status(host_a) == ""

    def test_same_host_tool_rewrite_of_the_checked_out_file_reads_clean(self, host_a: Path) -> None:
        _share_commit(host_a, ".zshrc", _home_line(host_a))

        # A host tool rewrites the file it read, spelling the host home again.
        (host_a / ".zshrc").unlink()
        (host_a / ".zshrc").write_bytes(_home_line(host_a))

        assert _status(host_a) == ""
        assert _index_bytes(host_a, ".zshrc") == _token_line()
        assert (host_a / ".zshrc").read_bytes() == _home_line(host_a)


class TestCheckoutSmudgesToTheCloningHost:
    def test_fresh_clone_checks_out_the_token_as_its_own_home(
        self, git_sandbox: Path, origin: Path, host_a: Path
    ) -> None:
        _share_commit(host_a, ".zshrc", _home_line(host_a))
        _push(host_a)

        host_b = _setup_host(origin, git_sandbox / "host-b")

        assert (host_b / ".zshrc").read_bytes() == _home_line(host_b)
        assert _index_bytes(host_b, ".zshrc") == _token_line()
        assert _status(host_b) == ""

    def test_setup_configures_the_filter_before_its_own_checkout(
        self, git_sandbox: Path, origin: Path, host_a: Path
    ) -> None:
        _share_commit(host_a, ".zshrc", _home_line(host_a))
        _push(host_a)
        host_b = git_sandbox / "host-b"
        host_b.mkdir()
        shell = _RecordingShell()

        result = CommandSetup(shell, str(host_b), str(origin)).execute()

        assert result.success, result.error
        configured_at = next(i for i, c in enumerate(shell.commands) if c.startswith(f"cfg config {FILTER_CLEAN_KEY} "))
        checked_out_at = shell.commands.index("cfg checkout --no-overwrite-ignore")
        assert configured_at < checked_out_at
        assert (host_b / ".zshrc").read_bytes() == _home_line(host_b)


class TestTwoHostPushPull:
    def test_pull_lands_the_pulling_host_home_and_keeps_the_index_tokenized(
        self, git_sandbox: Path, origin: Path, host_a: Path
    ) -> None:
        _share_commit(host_a, ".zshrc", _home_line(host_a))
        _push(host_a)
        host_b = _setup_host(origin, git_sandbox / "host-b")
        (host_a / ".zshrc").write_bytes(b"export TOOLS=" + _fs(host_a) + b"/tools\n")
        _run([*_git(host_a), "commit", "-qam", "A retargets TOOLS"], cwd=host_a)
        _push(host_a)

        result = _pull(host_b)

        assert result.success, result.error
        assert (host_b / ".zshrc").read_bytes() == b"export TOOLS=" + _fs(host_b) + b"/tools\n"
        assert _index_bytes(host_b, ".zshrc") == b"export TOOLS=" + TOKEN + b"/tools\n"
        assert _status(host_b) == ""


class TestAnchoredAttributeLine:
    def test_sharing_a_root_file_leaves_a_same_named_nested_file_untouched(self, host_a: Path) -> None:
        _track(host_a, "settings", _home_line(host_a))
        _track(host_a, "sub/settings", _home_line(host_a))
        _commit(host_a, "track both settings files")

        result = _share(host_a, "settings")

        assert result.success, result.error
        _commit(host_a, "share settings")
        assert (host_a / ".gitattributes").read_text() == "/settings filter=dot-host\n"
        assert _index_bytes(host_a, "settings") == _token_line()
        assert _index_bytes(host_a, "sub/settings") == _home_line(host_a)
        service = DotGitService(ShellAdapter(suppress_logging=True), str(host_a))
        assert service.check_attr_filter("settings") == "dot-host"
        assert service.check_attr_filter("sub/settings") is None

    def test_a_rewrite_of_the_nested_file_still_stores_the_literal_host_path(self, host_a: Path) -> None:
        _track(host_a, "settings", _home_line(host_a))
        _track(host_a, "sub/settings", _home_line(host_a))
        _commit(host_a, "track both settings files")
        assert _share(host_a, "settings").success
        _commit(host_a, "share settings")

        nested = _home_line(host_a) + b"export MORE=" + _fs(host_a) + b"/more\n"
        (host_a / "sub" / "settings").write_bytes(nested)
        _run([*_git(host_a), "add", "--", "sub/settings"], cwd=host_a)

        assert _index_bytes(host_a, "sub/settings") == nested
        assert TOKEN not in _index_bytes(host_a, "sub/settings")


class TestShellUnsafePaths:
    """Shell-unsafe names reach the filter intact.

    ``CommandShare`` refuses the space-bearing name (it needs attribute-file
    quoting, which is unsupported) and registers the leading-dash name
    successfully (``ls_files`` now guards the pathspec with ``--``; see
    ``test_share_succeeds_for_a_tracked_leading_dash_name`` below). The
    round-trip test still writes ``.gitattributes`` by hand for both names
    rather than going through ``CommandShare``, so it can exercise the space
    name's quoted round trip too, which ``CommandShare`` itself refuses.
    """

    @pytest.mark.parametrize("name", ["my file.conf", "-dashy.conf"])
    def test_shared_path_round_trips_through_clean_and_smudge(self, host_a: Path, name: str) -> None:
        _track(host_a, name, _home_line(host_a))
        _commit(host_a, f"track {name}")
        # %f reaches the filter shell-quoted, and the `--` guard in the configured
        # clean/smudge command keeps the leading dash out of the CLI's option parser.
        (host_a / ".gitattributes").write_text(f'"/{name}" filter=dot-host\n')
        _run([*_git(host_a), "add", "--renormalize", "--", name], cwd=host_a)
        _run([*_git(host_a), "add", "--", ".gitattributes"], cwd=host_a)
        _commit(host_a, f"share {name}")

        assert _index_bytes(host_a, name) == _token_line()
        assert _status(host_a) == ""

        (host_a / name).unlink()
        _run([*_git(host_a), "checkout", "--", name], cwd=host_a)

        assert (host_a / name).read_bytes() == _home_line(host_a)
        assert _status(host_a) == ""

    def test_share_refuses_a_path_it_cannot_anchor_unquoted(self, host_a: Path) -> None:
        name = "my file.conf"
        _track(host_a, name, _home_line(host_a))
        _commit(host_a, "track the spaced file")

        refused = _share(host_a, name)

        assert not refused.success
        assert refused.error == f"{name} needs attribute-file quoting, which is unsupported"
        assert not (host_a / ".gitattributes").exists()
        assert _index_bytes(host_a, name) == _home_line(host_a)

    def test_share_succeeds_for_a_tracked_leading_dash_name(self, host_a: Path) -> None:
        """``CommandShare`` must share a tracked leading-dash name, not report it untracked.

        Regression coverage for a review finding: ``DotGitService.ls_files``
        hands ``git ls-files`` an unguarded pathspec, so ``-dashy.conf`` is
        parsed as an option and the tracked-file check refuses it as
        untracked. See the class docstring above for the pre-fix workaround
        this test supersedes for the "tracked" check itself.
        """
        name = "-dashy.conf"
        _track(host_a, name, _home_line(host_a))
        _commit(host_a, f"track {name}")

        result = _share(host_a, name)

        assert result.success, result.error
        assert (host_a / ".gitattributes").read_text() == f"/{name} filter=dot-host\n"
        assert _index_bytes(host_a, name) == _token_line()


class TestRequiredFilterFailsLoudly:
    def test_missing_dot_fails_the_smudge_instead_of_writing_the_token(self, host_a: Path) -> None:
        _share_commit(host_a, ".zshrc", _home_line(host_a))
        (host_a / ".zshrc").unlink()
        no_dot = {**os.environ, "PATH": "/usr/bin:/bin"}

        proc = _run([*_git(host_a), "checkout", "--", ".zshrc"], cwd=host_a, env=no_dot, check=False)

        assert proc.returncode != 0
        assert b"dot-host" in proc.stderr
        assert not (host_a / ".zshrc").exists()

    def test_missing_dot_fails_the_clean_instead_of_staging_the_host_path(self, host_a: Path) -> None:
        _share_commit(host_a, ".zshrc", _home_line(host_a))
        edited = _home_line(host_a) + b"export EXTRA=" + _fs(host_a) + b"/extra\n"
        (host_a / ".zshrc").write_bytes(edited)
        no_dot = {**os.environ, "PATH": "/usr/bin:/bin"}

        proc = _run([*_git(host_a), "add", "--", ".zshrc"], cwd=host_a, env=no_dot, check=False)

        assert proc.returncode != 0
        assert b"dot-host" in proc.stderr
        assert _index_bytes(host_a, ".zshrc") == _token_line()
        assert (host_a / ".zshrc").read_bytes() == edited


class TestDivergenceWithSharedContent:
    def test_saved_patch_is_tokenized_and_rebuilds_the_edit_at_the_applying_home(
        self, git_sandbox: Path, origin: Path, host_a: Path
    ) -> None:
        _share_commit(host_a, ".zshrc", _home_line(host_a))
        _push(host_a)
        host_b = _setup_host(origin, git_sandbox / "host-b")
        (host_b / ".zshrc").write_bytes(_home_line(host_b) + b"export EXTRA=" + _fs(host_b) + b"/extra\n")
        (host_a / ".zshrc").write_bytes(b"export TOOLS=" + _fs(host_a) + b"/tools\n")
        _run([*_git(host_a), "commit", "-qam", "A retargets TOOLS"], cwd=host_a)
        _push(host_a)
        b_head = _head(host_b)

        result = _pull(host_b)

        assert result.success, result.error
        assert (host_b / ".zshrc").read_bytes() == b"export TOOLS=" + _fs(host_b) + b"/tools\n"
        [patch] = _patches(host_b)
        saved = patch.read_bytes()
        assert TOKEN in saved
        assert _fs(host_b) not in saved
        assert result.warnings[:2] == [
            f"divergence patch saved: {patch}",
            "reset to HEAD, local edit in patch: .zshrc",
        ]
        rebuilt = _apply_at(origin, b_head, patch, git_sandbox / "rebuilt")
        assert (rebuilt / ".zshrc").read_bytes() == (
            _home_line(rebuilt) + b"export EXTRA=" + _fs(rebuilt) + b"/extra\n"
        )

    def test_reverse_apply_restores_the_host_path_not_the_token(self, host_a: Path) -> None:
        _share_commit(host_a, ".zshrc", _home_line(host_a))
        service = DotGitService(ShellAdapter(suppress_logging=True), str(host_a))
        (host_a / ".zshrc").write_bytes(_home_line(host_a) + b"export EXTRA=" + _fs(host_a) + b"/extra\n")
        patch = service.diff(".zshrc")
        assert TOKEN.decode() in patch
        assert str(host_a) not in patch

        result = service.apply_reverse_to_worktree(patch)

        assert result.success, result.error
        assert (host_a / ".zshrc").read_bytes() == _home_line(host_a)
        assert _status(host_a) == ""


class TestIndexModeReadOnce:
    def test_execute_reads_the_stage_zero_index_mode_exactly_once(self, host_a: Path) -> None:
        """``execute()`` must capture the stage-zero index entry a single time.

        Regression coverage for a review finding (code-quality duplication):
        ``CommandShare`` currently reads the target's stage-zero index mode
        twice for one share - once through ``DotGitService.capture_index_entry``
        and once through its own private ``_index_mode``, both running
        ``git ls-files -s`` for the same path.
        """
        _track(host_a, ".zshrc", _home_line(host_a))
        _commit(host_a, "track .zshrc")
        shell = _RecordingShell()

        result = CommandShare(shell, str(host_a), ".zshrc").execute()

        assert result.success, result.error
        # Only the target counts: ``.gitattributes`` is captured once more so a
        # failed renormalize can restore its index entry exactly.
        ls_files_s_calls = [command for command in shell.commands if "ls-files -s" in command and ".zshrc" in command]
        assert len(ls_files_s_calls) == 1
