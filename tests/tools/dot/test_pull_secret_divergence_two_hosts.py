"""Two-host real-git tests: an edited git-secret file whose upstream copy changed.

Host B edits secret plaintext in place; host A changes the same secret and
pushes. B's pull must hide the edit first, so its ciphertext reaches the
divergence patch, then let upstream's plaintext win. Needs ``git-secret`` and
``gpg`` on ``PATH``; CI has neither, so CI skips this file.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter
from dot.commands.pull.pull import CommandPull
from dot.divergence import divergence_dir

from tests.tools.dot.conftest import _git, _run, _setup_bare_host

if TYPE_CHECKING:
    from collections.abc import Iterator

    from buvis.pybase.result import CommandResult

pytestmark = pytest.mark.skipif(
    shutil.which("git-secret") is None or shutil.which("gpg") is None, reason="needs git-secret and gpg"
)

KEY = "dot-test@test.local"
HINT = (
    "secret s.txt saved encrypted in patch; "
    "to read it, git apply the patch at its base commit and run git secret reveal there"
)


def _cmd(host: Path) -> list[str]:
    return _git(host / ".buvis", host)


@pytest.fixture
def secret_hosts(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Path, Path]]:
    # Not tmp_path: on macOS its length pushes the gpg-agent socket past the Unix socket
    # path limit and `git secret tell` fails.
    base = Path(tempfile.mkdtemp(prefix="dsd", dir="/tmp"))
    gnupg = base / "g"
    gnupg.mkdir(mode=0o700)
    monkeypatch.setenv("GNUPGHOME", str(gnupg))
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "Test User")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "test@test.local")
    try:
        _run(
            [
                "gpg",
                "--batch",
                "--pinentry-mode",
                "loopback",
                "--passphrase",
                "",
                "--quick-gen-key",
                KEY,
                "default",
                "default",
                "never",
            ]
        )
        origin = base / "origin.git"
        _run(["git", "init", "--bare", str(origin)])
        seed = base / "seed"
        _run(["git", "clone", str(origin), str(seed)])
        (seed / ".gitignore").write_text(".buvis\n")
        _run(["git", "secret", "init"], cwd=seed)
        _run(["git", "secret", "tell", KEY], cwd=seed)
        (seed / "s.txt").write_bytes(b"s base\n")
        (seed / "k.txt").write_bytes(b"k base\n")
        _run(["git", "secret", "add", "s.txt", "k.txt"], cwd=seed)
        _run(["git", "secret", "hide"], cwd=seed)
        _run(["git", "add", "-A"], cwd=seed)
        _run(["git", "commit", "-m", "seed"], cwd=seed)
        _run(["git", "push"], cwd=seed)
        host_a = _setup_bare_host(origin, base / "host_a")
        host_b = _setup_bare_host(origin, base / "host_b")
        for host in (host_a, host_b):
            _run([*_cmd(host), "secret", "reveal", "-f"])
        yield origin, host_a, host_b
    finally:
        for home in (gnupg, *base.glob("**/.gitsecret/keys")):
            subprocess.run(["gpgconf", "--homedir", str(home), "--kill", "all"], check=False, capture_output=True)
        shutil.rmtree(base, ignore_errors=True)


def _a_changes(host_a: Path, name: str, data: bytes) -> None:
    (host_a / name).write_bytes(data)
    _run([*_cmd(host_a), "secret", "hide", "-m"])
    _run([*_cmd(host_a), "add", f"{name}.secret", ".gitsecret/paths/mapping.cfg"])
    _run([*_cmd(host_a), "commit", "-m", f"A changes {name}"])
    _run([*_cmd(host_a), "push"])


def _pull(host: Path) -> CommandResult:
    return CommandPull(shell=ShellAdapter(suppress_logging=True), dotfiles_root=str(host)).execute()


def _patches(host: Path) -> list[Path]:
    d = divergence_dir(host)
    return sorted(d.glob("*.patch")) if d.is_dir() else []


def _base_of(patch: Path) -> str:
    line = next(ln for ln in patch.read_bytes().split(b"\n") if ln.startswith(b"# base: "))
    return line.removeprefix(b"# base: ").decode()


def _reveal_at_base(origin: Path, patch: Path, dest: Path) -> Path:
    _run(["git", "clone", "--quiet", str(origin), str(dest)])
    _run(["git", "-C", str(dest), "checkout", "--quiet", _base_of(patch)])
    _run(["git", "-C", str(dest), "apply", str(patch)])
    _run(["git", "secret", "reveal", "-f"], cwd=dest)
    return dest


class TestEditedSecretIsSavedEncrypted:
    def test_clashing_secret_edit_is_saved_as_ciphertext_and_rebuilds(
        self, secret_hosts: tuple[Path, Path, Path]
    ) -> None:
        origin, host_a, host_b = secret_hosts
        (host_b / "s.txt").write_bytes(b"s B edit\n")
        _a_changes(host_a, "s.txt", b"s A change\n")

        result = _pull(host_b)

        assert result.success, result.error
        assert (host_b / "s.txt").read_bytes() == b"s A change\n"
        [patch] = _patches(host_b)
        assert b"a/s.txt.secret" in patch.read_bytes()
        assert b"s B edit" not in patch.read_bytes()
        assert HINT in result.warnings
        fresh = _reveal_at_base(origin, patch, origin.parent / "fresh")
        assert (fresh / "s.txt").read_bytes() == b"s B edit\n"

    def test_secret_edit_untouched_upstream_is_kept_and_not_saved(self, secret_hosts: tuple[Path, Path, Path]) -> None:
        _origin, host_a, host_b = secret_hosts
        (host_b / "s.txt").write_bytes(b"s B edit\n")
        (host_b / "k.txt").write_bytes(b"k B edit\n")
        _a_changes(host_a, "s.txt", b"s A change\n")

        result = _pull(host_b)

        assert result.success, result.error
        assert (host_b / "s.txt").read_bytes() == b"s A change\n"
        assert (host_b / "k.txt").read_bytes() == b"k B edit\n"
        [patch] = _patches(host_b)
        assert b"a/s.txt.secret" in patch.read_bytes()
        assert b"a/k.txt.secret" not in patch.read_bytes()

    def test_missing_registered_plaintext_does_not_block_pull(self, secret_hosts: tuple[Path, Path, Path]) -> None:
        _origin, host_a, host_b = secret_hosts
        (host_b / "k.txt").unlink()
        (host_b / "s.txt").write_bytes(b"s B edit\n")
        _a_changes(host_a, "s.txt", b"s A change\n")

        result = _pull(host_b)

        assert result.success, result.error
        [patch] = _patches(host_b)
        assert b"a/s.txt.secret" in patch.read_bytes()
        assert (host_b / "k.txt").read_bytes() == b"k base\n"
