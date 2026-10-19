"""Tests for the shared-file opt-in command."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.result import CommandResult
from dot.commands.localize.share import CommandShare
from dot.git.models import IndexEntry
from dot.hostfilter import TOKEN
from dot.hostlinks.manifest import MANIFEST_PATH, read_manifest

ATTRS_PRELUDE = "*.png binary\n*.jpg -text\n"
PLAIN_ENTRY = IndexEntry(mode="100644", sha="a" * 40)
LINK_ENTRY = IndexEntry(mode="120000", sha="b" * 40)


def _command_text(call: object) -> str:
    """Join every argument of a recorded shell call into one string."""
    args = getattr(call, "args", ())
    kwargs = getattr(call, "kwargs", {})
    return " ".join(str(value) for value in (*args, *kwargs.values()))


def _index_read(*args: object, **kwargs: object) -> tuple[str, str]:
    """Return a regular-file index line for the path the command asks about."""
    parts = [str(value) for value in (*args, *kwargs.values())]
    command = next((part for part in parts if "ls-files" in part), parts[0] if parts else "")
    token = command.split()[-1] if command.split() else ""
    path = token.removeprefix(":(literal)").strip("'\"")
    return "", f"{PLAIN_ENTRY.mode} {PLAIN_ENTRY.sha} 0\t{path}"


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.side_effect = _index_read
    return mock


def canned_index_read(shell: MagicMock, read: tuple[str, str]) -> None:
    """Make every shell read return the same canned result pair."""
    shell.exe.side_effect = lambda *_args, **_kwargs: read


def index_read_commands(shell: MagicMock) -> list[str]:
    """Return the text of every shell call that read the git index."""
    texts = [_command_text(call) for call in shell.exe.call_args_list]
    return [text for text in texts if "ls-files" in text]


def host_text(root: Path, count: int) -> str:
    """Return file text holding count boundary-matched copies of root."""
    return "".join(f"key{index} = {root}\n" for index in range(count)) + "plain tail\n"


def write_file(root: Path, rel: str, text: str) -> Path:
    """Create a work-tree file under root and return its path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def make_service(
    *,
    tracked: set[str],
    secrets: list[str] | None = None,
    configured: bool = True,
    attr: str | None = "dot-host",
    entry: IndexEntry | None = PLAIN_ENTRY,
    renormalize: CommandResult | None = None,
    stage: CommandResult | None = None,
    restore: CommandResult | None = None,
) -> MagicMock:
    """Build a fully stubbed DotGitService double."""
    service = MagicMock()
    service.ls_files.side_effect = lambda spec: {spec} if spec in tracked else set()
    service.list_secrets.return_value = list(secrets or [])
    service.filter_driver_configured.return_value = configured
    service.check_attr_filter.return_value = attr
    service.capture_index_entry.side_effect = lambda path: None if path == ".gitattributes" else entry
    service.renormalize.return_value = renormalize or CommandResult(success=True)
    service.stage.return_value = stage or CommandResult(success=True)
    service.restore_index_entry.return_value = restore or CommandResult(success=True)
    return service


def assert_index_untouched(service: MagicMock) -> None:
    """Assert no index-changing service call was made."""
    service.renormalize.assert_not_called()
    service.stage.assert_not_called()
    service.restore_index_entry.assert_not_called()


class TestCommandShareRefusals:
    def test_refuses_untracked_path(self, tmp_path: Path, shell: MagicMock) -> None:
        target = write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        before = target.read_bytes()
        service = make_service(tracked={".zshrc.bak"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc not tracked; run dot add first"
        assert target.read_bytes() == before
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)

    def test_refuses_directory(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".config/app/settings.json", "{}\n")
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".config/app"})

        result = CommandShare(shell, str(tmp_path), ".config/app", git_service=service).execute()

        assert not result.success
        assert result.error == ".config/app is a directory; directory opt-in is unsupported"
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)

    def test_refuses_git_secret_file(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".ssh/config", host_text(tmp_path, 1))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".ssh/config"}, secrets=[".ssh/config"])

        result = CommandShare(shell, str(tmp_path), ".ssh/config", git_service=service).execute()

        assert not result.success
        assert result.error == ".ssh/config is a git-secret file; shared opt-in refused"
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)

    @pytest.mark.parametrize(
        "manifest_text",
        [
            ".vimrc => .local/.vimrc\n.zshrc => .local/.zshrc\n",
            ".zshrc=>.local/.zshrc\n",
            "   .zshrc   =>   .local/.zshrc   \n",
        ],
        ids=["spaced", "unspaced", "padded"],
    )
    def test_refuses_host_links_target(self, tmp_path: Path, shell: MagicMock, manifest_text: str) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        manifest = write_file(tmp_path, MANIFEST_PATH, manifest_text)
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc already listed in host-links manifest"
        assert manifest.read_text() == manifest_text
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    def test_refuses_gitattributes_itself(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".gitattributes"})

        result = CommandShare(shell, str(tmp_path), ".gitattributes", git_service=service).execute()

        assert not result.success
        assert result.error == "refused: .gitattributes itself cannot be shared"
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)

    def test_refuses_path_already_registered(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        attrs_text = ATTRS_PRELUDE + "/.zshrc filter=dot-host\n"
        write_file(tmp_path, ".gitattributes", attrs_text)
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc already has a dot-host filter line"
        assert (tmp_path / ".gitattributes").read_text() == attrs_text
        assert_index_untouched(service)

    def test_refuses_reserved_token_in_bytes(self, tmp_path: Path, shell: MagicMock) -> None:
        target = write_file(tmp_path, ".zshrc", f"home = {TOKEN.decode()}\n")
        before = target.read_bytes()
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc contains the reserved @HOME@ token"
        assert target.read_bytes() == before
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    def test_refuses_tracked_file_missing_from_disk(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc is tracked but missing from disk; run dot add or restore it first"
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)

    @pytest.mark.parametrize("rel", [".config/*.conf", ".config/a?.conf", ".config/a[1].conf"])
    def test_refuses_glob_bearing_path(self, tmp_path: Path, shell: MagicMock, rel: str) -> None:
        write_file(tmp_path, rel, "plain\n")
        service = make_service(tracked={rel})

        result = CommandShare(shell, str(tmp_path), rel, git_service=service).execute()

        assert not result.success
        assert result.error == f"{rel} looks like a glob pattern; glob opt-in is unsupported"
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    @pytest.mark.parametrize(
        "rel",
        [
            ".config/my conf",
            ".config/note#1",
            ".config/bang!",
            ".config/back\\slash",
            ".config/tab\there",
            ".config/trail ",
        ],
    )
    def test_refuses_path_needing_attribute_quoting(self, tmp_path: Path, shell: MagicMock, rel: str) -> None:
        write_file(tmp_path, rel, "plain\n")
        service = make_service(tracked={rel})

        result = CommandShare(shell, str(tmp_path), rel, git_service=service).execute()

        assert not result.success
        assert result.error == f"{rel} needs attribute-file quoting, which is unsupported"
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    def test_refuses_when_filter_driver_not_configured(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".zshrc"}, configured=False)

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == (
            "dot-host filter driver is not configured; a prior self-heal write may have failed. "
            "Re-run 'dot status' to retry, then 'dot localize --shared .zshrc' again"
        )
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)

    def test_refuses_symlinked_target(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".local/.zshrc", "plain\n")
        (tmp_path / ".zshrc").symlink_to(".local/.zshrc")
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc is not a plain tracked file (symlink or special mode); shared opt-in refused"
        assert (tmp_path / ".zshrc").is_symlink()
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    def test_refuses_non_regular_index_mode(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        canned_index_read(shell, ("", f"120000 {LINK_ENTRY.sha} 0\t.zshrc"))
        service = make_service(tracked={".zshrc"}, entry=LINK_ENTRY)

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc is not a plain tracked file (symlink or special mode); shared opt-in refused"
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    def test_refuses_target_with_no_captured_index_entry(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".zshrc"}, entry=None)

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc is not a plain tracked file (symlink or special mode); shared opt-in refused"
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)

    @pytest.mark.parametrize("read", [("fatal: not a git repository", ""), ("", ""), ("", "\n")])
    def test_refuses_target_whose_index_mode_read_fails(
        self,
        tmp_path: Path,
        shell: MagicMock,
        read: tuple[str, str],
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        canned_index_read(shell, read)
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == ".zshrc is not a plain tracked file (symlink or special mode); shared opt-in refused"
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)

    @pytest.mark.parametrize("rel", ["../outside.conf", "../../etc/hosts", "../deep/nested/other.cfg"])
    def test_refuses_relative_path_escaping_dotfiles_root(
        self,
        tmp_path: Path,
        shell: MagicMock,
        rel: str,
    ) -> None:
        escaped = Path(os.path.normpath(tmp_path / rel))
        escaped.parent.mkdir(parents=True, exist_ok=True)
        escaped.write_text("stranger\n")
        service = make_service(tracked={rel, Path(rel).name, str(escaped)})

        result = CommandShare(shell, str(tmp_path), rel, git_service=service).execute()

        assert not result.success
        assert escaped.read_text() == "stranger\n"
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    def test_refuses_absolute_path_outside_dotfiles_root(self, tmp_path: Path, shell: MagicMock) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-stranger.conf"
        outside.write_text("stranger\n")
        service = make_service(tracked={str(outside), outside.name})

        result = CommandShare(shell, str(tmp_path), str(outside), git_service=service).execute()

        assert not result.success
        assert outside.read_text() == "stranger\n"
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    def test_refuses_path_escaping_root_through_a_symlinked_directory(
        self,
        tmp_path: Path,
        shell: MagicMock,
    ) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-elsewhere"
        outside.mkdir()
        (outside / "linked.conf").write_text("stranger\n")
        (tmp_path / "link").symlink_to(outside, target_is_directory=True)
        service = make_service(tracked={"link/linked.conf"})

        result = CommandShare(shell, str(tmp_path), "link/linked.conf", git_service=service).execute()

        assert not result.success
        assert (outside / "linked.conf").read_text() == "stranger\n"
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)


class TestCommandShareSuccess:
    @pytest.mark.parametrize(("rel", "count"), [(".zshrc", 2), (".config/app/settings.json", 3)])
    def test_reports_replaced_host_value_count(
        self,
        tmp_path: Path,
        shell: MagicMock,
        rel: str,
        count: int,
    ) -> None:
        target = write_file(tmp_path, rel, host_text(tmp_path, count))
        before = target.read_bytes()
        service = make_service(tracked={rel})

        result = CommandShare(shell, str(tmp_path), rel, git_service=service).execute()

        assert result.success, result.error
        assert result.output == f"shared {rel}: {count} host value(s) replaced"
        assert result.info == ["staged .gitattributes"]
        assert target.read_bytes() == before
        service.renormalize.assert_called_once_with(rel)
        service.stage.assert_called_once_with(".gitattributes")

    @pytest.mark.parametrize(
        ("template", "count"),
        [
            ("path = {root}_backup/x\nother = {root}abc\nkey0 = {root}\n", 1),
            ("a = {root}/sub\nb = {root}/\n", 2),
        ],
        ids=["suffix-glued", "trailing-slash"],
    )
    def test_counts_only_boundary_matched_host_values(
        self,
        tmp_path: Path,
        shell: MagicMock,
        template: str,
        count: int,
    ) -> None:
        write_file(tmp_path, ".zshrc", template.format(root=tmp_path))
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert result.success, result.error
        assert result.output == f"shared .zshrc: {count} host value(s) replaced"

    @pytest.mark.parametrize(
        "template",
        ["", "plain tail\n", "path = {root}_backup/x\nother = {root}abc\n"],
        ids=["empty", "plain", "non-boundary-only"],
    )
    def test_reports_zero_host_values(self, tmp_path: Path, shell: MagicMock, template: str) -> None:
        write_file(tmp_path, ".zshrc", template.format(root=tmp_path))
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert result.success, result.error
        assert result.output == "no host value found in .zshrc; filter active for future writes"
        assert result.info == ["staged .gitattributes"]
        assert (tmp_path / ".gitattributes").read_text() == "/.zshrc filter=dot-host\n"
        service.renormalize.assert_called_once_with(".zshrc")
        service.stage.assert_called_once_with(".gitattributes")

    @pytest.mark.parametrize(
        ("existing", "expected"),
        [
            (None, "/.zshrc filter=dot-host\n"),
            (ATTRS_PRELUDE, ATTRS_PRELUDE + "/.zshrc filter=dot-host\n"),
            ("*.png binary\n*.jpg -text", ATTRS_PRELUDE + "/.zshrc filter=dot-host\n"),
        ],
    )
    def test_appends_anchored_line_honouring_newline_convention(
        self,
        tmp_path: Path,
        shell: MagicMock,
        existing: str | None,
        expected: str,
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        if existing is not None:
            write_file(tmp_path, ".gitattributes", existing)
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert result.success, result.error
        assert (tmp_path / ".gitattributes").read_text() == expected

    def test_accepts_absolute_path_under_root(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".config/app/settings.json", host_text(tmp_path, 2))
        service = make_service(tracked={".config/app/settings.json"})
        absolute = str(tmp_path / ".config/app/settings.json")

        result = CommandShare(shell, str(tmp_path), absolute, git_service=service).execute()

        assert result.success, result.error
        assert result.output == "shared .config/app/settings.json: 2 host value(s) replaced"
        assert (tmp_path / ".gitattributes").read_text() == "/.config/app/settings.json filter=dot-host\n"
        service.renormalize.assert_called_once_with(".config/app/settings.json")

    @pytest.mark.parametrize(
        ("rel", "existing"),
        [
            (".zshrc", "/.zshrc.local filter=dot-host\n"),
            (".zshrc.local", "/.zshrc filter=dot-host\n"),
            (".zshrc", "/sub/.zshrc filter=dot-host\n"),
            (".zshrc", "#/.zshrc filter=dot-host\n"),
        ],
        ids=["suffix-neighbour", "shorter-neighbour", "nested-neighbour", "commented"],
    )
    def test_shares_path_whose_neighbour_is_registered(
        self,
        tmp_path: Path,
        shell: MagicMock,
        rel: str,
        existing: str,
    ) -> None:
        write_file(tmp_path, rel, host_text(tmp_path, 1))
        write_file(tmp_path, ".gitattributes", existing)
        service = make_service(tracked={rel}, secrets=[f"{rel}.bak"])

        result = CommandShare(shell, str(tmp_path), rel, git_service=service).execute()

        assert result.success, result.error
        assert (tmp_path / ".gitattributes").read_text() == existing + f"/{rel} filter=dot-host\n"

    @pytest.mark.parametrize(
        "manifest_text",
        [
            "# .zshrc => .local/.zshrc\n",
            ".zshrc\n",
            "sub/.zshrc => .local/.zshrc\n",
        ],
        ids=["commented", "missing-arrow", "nested-target"],
    )
    def test_shares_path_that_no_valid_manifest_entry_claims(
        self,
        tmp_path: Path,
        shell: MagicMock,
        manifest_text: str,
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        write_file(tmp_path, MANIFEST_PATH, manifest_text)
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert result.success, result.error
        assert (tmp_path / ".gitattributes").read_text() == "/.zshrc filter=dot-host\n"
        assert (tmp_path / MANIFEST_PATH).read_text() == manifest_text

    def test_reads_index_mode_with_a_pathspec_for_the_target(self, tmp_path: Path, shell: MagicMock) -> None:
        rel = ".config/app/settings.json"
        write_file(tmp_path, rel, host_text(tmp_path, 1))
        service = make_service(tracked={rel})

        result = CommandShare(shell, str(tmp_path), rel, git_service=service).execute()

        assert result.success, result.error
        reads = index_read_commands(shell)
        assert reads
        assert all(rel in text for text in reads)

    def test_leaves_file_location_and_manifest_untouched(self, tmp_path: Path, shell: MagicMock) -> None:
        target = write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        before = target.read_bytes()
        write_file(tmp_path, MANIFEST_PATH, ".vimrc => .local/.vimrc\n")
        service = make_service(tracked={".zshrc"})

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert result.success, result.error
        assert target.is_file()
        assert not target.is_symlink()
        assert target.read_bytes() == before
        assert not (tmp_path / ".local").exists()
        assert (tmp_path / MANIFEST_PATH).read_text() == ".vimrc => .local/.vimrc\n"
        links, errors = read_manifest(tmp_path)
        assert errors == []
        assert [(link.target, link.source) for link in links] == [(".vimrc", ".local/.vimrc")]

    def test_writes_attribute_before_check_then_renormalizes_then_stages(
        self,
        tmp_path: Path,
        shell: MagicMock,
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        attrs = tmp_path / ".gitattributes"
        order: list[str] = []

        def registered() -> bool:
            return attrs.exists() and "/.zshrc filter=dot-host\n" in attrs.read_text()

        def on_check(path: str) -> str:
            order.append(f"check_attr:{path}:{registered()}")
            return "dot-host"

        def on_renormalize(path: str) -> CommandResult:
            order.append(f"renormalize:{path}:{registered()}")
            return CommandResult(success=True)

        def on_stage(path: str) -> CommandResult:
            order.append(f"stage:{path}:{registered()}")
            return CommandResult(success=True)

        service = make_service(tracked={".zshrc"})
        service.check_attr_filter.side_effect = on_check
        service.renormalize.side_effect = on_renormalize
        service.stage.side_effect = on_stage

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert result.success, result.error
        assert order == [
            "check_attr:.zshrc:True",
            "renormalize:.zshrc:True",
            "stage:.gitattributes:True",
        ]

    def test_builds_default_git_service_from_shell_and_root(self, tmp_path: Path, shell: MagicMock) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))

        with patch("dot.commands.localize.share.DotGitService") as service_cls:
            service_cls.return_value = make_service(tracked={".zshrc"})
            result = CommandShare(shell, str(tmp_path), ".zshrc").execute()

        assert result.success, result.error
        assert result.output == "shared .zshrc: 2 host value(s) replaced"
        passed = service_cls.call_args.args + tuple(service_cls.call_args.kwargs.values())
        assert shell in passed
        assert str(tmp_path) in passed


class TestCommandShareRollback:
    @pytest.mark.parametrize("effective", ["lfs", None])
    def test_conflicting_effective_filter_restores_prior_attributes(
        self,
        tmp_path: Path,
        shell: MagicMock,
        effective: str | None,
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".zshrc"}, attr=effective)

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == (
            f".zshrc is governed by a conflicting attribute entry (effective filter: {effective!r}); "
            "check nested .gitattributes files and $GIT_DIR/info/attributes for a prior rule on this path"
        )
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        service.renormalize.assert_not_called()
        service.stage.assert_not_called()

    def test_conflicting_effective_filter_removes_created_attributes_file(
        self,
        tmp_path: Path,
        shell: MagicMock,
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        service = make_service(tracked={".zshrc"}, attr="lfs")

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert not (tmp_path / ".gitattributes").exists()
        service.renormalize.assert_not_called()
        service.stage.assert_not_called()

    def test_renormalize_failure_restores_prior_attributes(self, tmp_path: Path, shell: MagicMock) -> None:
        target = write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        before = target.read_bytes()
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(
            tracked={".zshrc"},
            renormalize=CommandResult(success=False, error="cfg add exploded"),
        )

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == "renormalize failed: cfg add exploded"
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert target.read_bytes() == before
        service.stage.assert_not_called()
        service.restore_index_entry.assert_not_called()

    @pytest.mark.parametrize(
        ("rel", "entry"),
        [(".zshrc", PLAIN_ENTRY), (".config/app/settings.json", IndexEntry(mode="100755", sha="c" * 40))],
    )
    def test_stage_failure_rolls_back_by_captured_index_entry(
        self,
        tmp_path: Path,
        shell: MagicMock,
        rel: str,
        entry: IndexEntry,
    ) -> None:
        write_file(tmp_path, rel, host_text(tmp_path, 1))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        canned_index_read(shell, ("", f"{entry.mode} {entry.sha} 0\t{rel}"))
        service = make_service(
            tracked={rel},
            entry=entry,
            stage=CommandResult(success=False, error="cfg add failed"),
        )

        result = CommandShare(shell, str(tmp_path), rel, git_service=service).execute()

        assert not result.success
        assert result.error == (
            f"could not stage .gitattributes: cfg add failed; share rolled back, retry 'dot localize --shared {rel}'"
        )
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        service.restore_index_entry.assert_called_once_with(rel, entry)

    def test_stage_failure_restores_the_entry_captured_before_renormalize(
        self,
        tmp_path: Path,
        shell: MagicMock,
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        pre_entry = IndexEntry(mode="100644", sha="d" * 40)
        tokenized_entry = IndexEntry(mode="100644", sha="e" * 40)
        order: list[str] = []

        def on_capture(path: str) -> IndexEntry | None:
            order.append("capture")
            if path == ".gitattributes":
                return None
            return tokenized_entry if "renormalize" in order else pre_entry

        def on_renormalize(_path: str) -> CommandResult:
            order.append("renormalize")
            return CommandResult(success=True)

        service = make_service(tracked={".zshrc"}, stage=CommandResult(success=False, error="cfg add failed"))
        service.capture_index_entry.side_effect = on_capture
        service.renormalize.side_effect = on_renormalize

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert "capture" in order[: order.index("renormalize")]
        assert "capture" not in order[order.index("renormalize") :]
        service.restore_index_entry.assert_called_once_with(".zshrc", pre_entry)
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE

    def test_failed_rollback_after_stage_failure_does_not_claim_rollback(
        self,
        tmp_path: Path,
        shell: MagicMock,
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(
            tracked={".zshrc"},
            stage=CommandResult(success=False, error="cfg add failed"),
            restore=CommandResult(success=False, error="update-index refused"),
        )

        result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        assert not result.success
        assert result.error == (
            "could not stage .gitattributes: cfg add failed; ROLLBACK FAILED (update-index refused); "
            ".zshrc's index entry may still be tokenized — run 'cfg status' and "
            "'dot run diff --cached -- .zshrc' before retrying"
        )
        assert "rolled back, retry" not in result.error
        service.restore_index_entry.assert_called_once_with(".zshrc", PLAIN_ENTRY)

    @pytest.mark.parametrize(
        ("stage", "expected_entries"),
        [
            (CommandResult(success=True), []),
            (CommandResult(success=False, error="cfg add failed"), [PLAIN_ENTRY]),
        ],
        ids=["stage-succeeds", "stage-fails"],
    )
    def test_never_restores_target_index_entry_from_a_none_capture(
        self,
        tmp_path: Path,
        shell: MagicMock,
        stage: CommandResult,
        expected_entries: list[IndexEntry],
    ) -> None:
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".zshrc"}, stage=stage)

        CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()

        restored = [(call.args[0], call.args[1]) for call in service.restore_index_entry.call_args_list]
        assert [entry for path, entry in restored if path == ".zshrc"] == expected_entries
        assert [entry for path, entry in restored if entry is None] == []


class TestCommandShareFilesystemErrors:
    def test_unreadable_target_returns_failure_result(self, tmp_path: Path, shell: MagicMock) -> None:
        if os.geteuid() == 0:
            pytest.skip("root bypasses file permissions")
        target = write_file(tmp_path, ".zshrc", host_text(tmp_path, 1))
        target.chmod(0o000)
        service = make_service(tracked={".zshrc"})

        try:
            result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()
        finally:
            target.chmod(0o600)

        assert not result.success
        assert result.error
        assert not (tmp_path / ".gitattributes").exists()
        assert_index_untouched(service)

    def test_unwritable_attributes_file_returns_failure_result(self, tmp_path: Path, shell: MagicMock) -> None:
        if os.geteuid() == 0:
            pytest.skip("root bypasses file permissions")
        write_file(tmp_path, ".zshrc", host_text(tmp_path, 2))
        write_file(tmp_path, ".gitattributes", ATTRS_PRELUDE)
        service = make_service(tracked={".zshrc"})
        tmp_path.chmod(0o500)

        try:
            result = CommandShare(shell, str(tmp_path), ".zshrc", git_service=service).execute()
        finally:
            tmp_path.chmod(0o700)

        assert not result.success
        assert result.error
        assert (tmp_path / ".gitattributes").read_text() == ATTRS_PRELUDE
        assert_index_untouched(service)
