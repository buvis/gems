"""Tests for tiromex path resolution, confinement, note listing and tx state."""

from __future__ import annotations

import builtins
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from bim.commands.tx.export_claims import CommandTxExportClaims
from bim.commands.tx.shared.claims import collect_claims
from bim.commands.tx.shared.format import read_note
from bim.commands.tx.shared.paths import (
    TiromexPaths,
    confine,
    iter_note_files,
    read_last_maintain,
    resolve_tiromex,
    to_vault_rel,
    tx_state_dir,
)
from bim.commands.tx.status import CommandTxStatus
from bim.commands.tx.validate import CommandTxValidate
from bim.dependencies import get_tiromex_paths
from bim.settings import BimSettings

if TYPE_CHECKING:
    from tests.tools.bim.tx.conftest import TxNoteBuilder, TxVault


@pytest.fixture
def paths(tx_vault: TxVault) -> TiromexPaths:
    return resolve_tiromex(tx_vault.zettelkasten, "tiromex")


@pytest.fixture
def other_vault(tx_vault: TxVault) -> Path:
    """A second vault, ``<base>/other/kb/tx``, with different folder names."""
    zettelkasten = tx_vault.root.parent / "other" / "kb"
    (zettelkasten / "tx").mkdir(parents=True)
    return zettelkasten


class TestResolveTiromex:
    def test_resolves_vault_root_zettelkasten_and_folder(self, tx_vault: TxVault) -> None:
        assert resolve_tiromex(tx_vault.zettelkasten, "tiromex") == TiromexPaths(
            vault_root=tx_vault.root,
            zettelkasten=tx_vault.zettelkasten,
            folder=tx_vault.folder,
        )

    def test_uses_the_given_zettelkasten_and_folder(self, other_vault: Path) -> None:
        assert resolve_tiromex(other_vault, "tx") == TiromexPaths(
            vault_root=other_vault.parent,
            zettelkasten=other_vault,
            folder=other_vault / "tx",
        )

    def test_relative_zettelkasten_resolves_against_cwd(
        self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tx_vault.root.parent)

        result = resolve_tiromex(Path("vault/notes"), "tiromex")

        assert result.zettelkasten == tx_vault.zettelkasten
        assert result.vault_root == tx_vault.root

    @pytest.mark.parametrize("name", ["atlas", "..atlas", ".tiromex"])
    def test_accepts_missing_single_part_folder_without_creating_it(self, tx_vault: TxVault, name: str) -> None:
        result = resolve_tiromex(tx_vault.zettelkasten, name)

        assert result.folder == tx_vault.zettelkasten / name
        assert not result.folder.exists()

    @pytest.mark.parametrize("name", ["", "/tiromex", "tiromex/sub", ".", "..", "../tiromex", "./tiromex/.."])
    def test_rejects_bad_folder_name(self, tx_vault: TxVault, name: str) -> None:
        with pytest.raises(ValueError):
            resolve_tiromex(tx_vault.zettelkasten, name)

    def test_rejects_absolute_folder_name_even_when_it_is_the_folder(self, tx_vault: TxVault) -> None:
        with pytest.raises(ValueError):
            resolve_tiromex(tx_vault.zettelkasten, str(tx_vault.folder))

    def test_rejects_missing_zettelkasten(self, tx_vault: TxVault) -> None:
        with pytest.raises(ValueError):
            resolve_tiromex(tx_vault.root / "absent", "tiromex")

    def test_rejects_zettelkasten_that_is_a_file(self, tx_vault: TxVault) -> None:
        not_a_dir = tx_vault.root / "notes.md"
        not_a_dir.write_text("x", encoding="utf-8")

        with pytest.raises(ValueError):
            resolve_tiromex(not_a_dir, "tiromex")

    @pytest.mark.parametrize("target", ["self", "sibling", "outside", "dangling"])
    def test_rejects_symlinked_folder(self, tx_vault: TxVault, target: str) -> None:
        zettelkasten = tx_vault.zettelkasten
        (zettelkasten / "private").mkdir()
        outside = tx_vault.root.parent / "elsewhere"
        outside.mkdir()
        destinations = {
            "self": Path("."),
            "sibling": zettelkasten / "private",
            "outside": outside,
            "dangling": zettelkasten / "nothing-here",
        }
        (zettelkasten / "linked").symlink_to(destinations[target], target_is_directory=True)

        with pytest.raises(ValueError):
            resolve_tiromex(zettelkasten, "linked")

    def test_symlinked_zettelkasten_gives_real_vault_root(self, tx_vault: TxVault) -> None:
        real = tx_vault.root.parent / "real-vault" / "notes"
        (real / "tiromex").mkdir(parents=True)
        alias = tx_vault.root.parent / "alias-notes"
        alias.symlink_to(real, target_is_directory=True)

        result = resolve_tiromex(alias, "tiromex")

        assert result == TiromexPaths(vault_root=real.parent, zettelkasten=real, folder=real / "tiromex")
        assert result.vault_root != alias.parent


class TestConfine:
    @pytest.mark.parametrize(
        ("vault_rel", "expected"),
        [
            ("notes/tiromex/20260411145300.md", ("20260411145300.md",)),
            ("notes/tiromex/sub/20260411145301.md", ("sub", "20260411145301.md")),
            ("notes/tiromex/./20260411145302.md", ("20260411145302.md",)),
        ],
    )
    def test_returns_resolved_path_inside_folder_without_requiring_file(
        self, paths: TiromexPaths, vault_rel: str, expected: tuple[str, ...]
    ) -> None:
        result = confine(paths, vault_rel)

        assert result == paths.folder.joinpath(*expected)
        assert not result.exists()

    @pytest.mark.parametrize(
        "vault_rel",
        [
            "",
            "/notes/tiromex/x.md",
            "notes/tiromex/../tiromex/x.md",
            "../vault/notes/tiromex/x.md",
            "notes/private.md",
            "notes/tiromex-old/x.md",
            "notes/tiromexx.md",
            "notes/x.md",
        ],
    )
    def test_rejects_absolute_dotdot_and_outside_paths(self, paths: TiromexPaths, vault_rel: str) -> None:
        with pytest.raises(ValueError):
            confine(paths, vault_rel)

    def test_rejects_absolute_path_into_the_folder(self, paths: TiromexPaths) -> None:
        with pytest.raises(ValueError):
            confine(paths, (paths.folder / "x.md").as_posix())

    def test_rejects_symlinked_note_leaving_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        private = tx_notes.write(tx_notes.concept(), "private", folder=paths.zettelkasten)
        (paths.folder / "leak.md").symlink_to(private)

        with pytest.raises(ValueError):
            confine(paths, "notes/tiromex/leak.md")

    def test_rejects_path_through_symlinked_dir_leaving_folder(self, paths: TiromexPaths) -> None:
        outside = paths.vault_root.parent / "outside"
        outside.mkdir()
        (paths.folder / "outdir").symlink_to(outside, target_is_directory=True)

        with pytest.raises(ValueError):
            confine(paths, "notes/tiromex/outdir/x.md")

    @pytest.mark.parametrize("error", [RuntimeError("Symlink loop from 'loop.md'"), OSError(40, "Too many levels")])
    def test_resolution_failure_becomes_value_error(
        self, paths: TiromexPaths, monkeypatch: pytest.MonkeyPatch, error: Exception
    ) -> None:
        real_resolve = Path.resolve

        def resolve(self: Path, strict: bool = False) -> Path:
            if self.name == "loop.md":
                raise error
            return real_resolve(self, strict)

        monkeypatch.setattr(Path, "resolve", resolve)

        with pytest.raises(ValueError, match="loop.md") as caught:
            confine(paths, "notes/tiromex/loop.md")
        assert caught.value.__cause__ is error

    def test_real_symlink_loop_never_escapes_as_another_error(self, paths: TiromexPaths) -> None:
        (paths.folder / "loop.md").symlink_to(paths.folder / "loop2.md")
        (paths.folder / "loop2.md").symlink_to(paths.folder / "loop.md")

        try:
            confine(paths, "notes/tiromex/loop.md")
        except ValueError:
            pass

    def test_follows_symlink_that_stays_inside_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        real = tx_notes.write(tx_notes.concept(), "20260411145300")
        (paths.folder / "alias.md").symlink_to(real)

        assert confine(paths, "notes/tiromex/alias.md") == real

    def test_resolves_against_the_given_vault_root(self, other_vault: Path) -> None:
        other = resolve_tiromex(other_vault, "tx")

        assert confine(other, "kb/tx/a.md") == other_vault / "tx" / "a.md"
        with pytest.raises(ValueError):
            confine(other, "notes/tiromex/a.md")

    def test_symlinked_zettelkasten_confines_into_real_folder(self, tx_vault: TxVault) -> None:
        alias = tx_vault.root.parent / "alias-notes"
        alias.symlink_to(tx_vault.zettelkasten, target_is_directory=True)

        result = confine(resolve_tiromex(alias, "tiromex"), "notes/tiromex/x.md")

        assert result == tx_vault.folder / "x.md"


class TestToVaultRel:
    @pytest.mark.parametrize(
        ("parts", "expected"),
        [
            (("tiromex", "20260411145300.md"), "notes/tiromex/20260411145300.md"),
            (("tiromex", "sub", "a.md"), "notes/tiromex/sub/a.md"),
            (("private.md",), "notes/private.md"),
        ],
    )
    def test_returns_posix_path_relative_to_vault_root(
        self, paths: TiromexPaths, parts: tuple[str, ...], expected: str
    ) -> None:
        result = to_vault_rel(paths, paths.zettelkasten.joinpath(*parts))

        assert isinstance(result, str)
        assert result == expected

    def test_uses_the_given_vault_root(self, other_vault: Path) -> None:
        other = resolve_tiromex(other_vault, "tx")

        assert to_vault_rel(other, other_vault / "tx" / "a.md") == "kb/tx/a.md"


class TestIterNoteFiles:
    def test_returns_sorted_md_files_recursively(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        folder = paths.folder
        tx_notes.write(tx_notes.concept("20260412090000", "Belief needs grounds"), "20260412090000", folder / "sub")
        tx_notes.write(tx_notes.plain(), "20260411160000")
        tx_notes.write(tx_notes.concept(), "20260411145300")
        tx_notes.write(tx_notes.run(), "20260411150000")
        tx_notes.write(tx_notes.index(), "20260411140000")
        tx_notes.write(tx_notes.plain("20260413000000", "Draft"), "20260413000000", folder / "drafts.md")
        tx_notes.write(tx_notes.plain("20260414000000", "Deep"), "20260414000000", folder / "a" / "b" / "c")
        (folder / "notes.txt").write_text("x", encoding="utf-8")
        (folder / "20260411145300.md.bak").write_text("x", encoding="utf-8")
        (folder / "readme.markdown").write_text("x", encoding="utf-8")
        (folder / "xmd").write_text("x", encoding="utf-8")

        assert iter_note_files(paths) == [
            folder / "20260411140000.md",
            folder / "20260411145300.md",
            folder / "20260411150000.md",
            folder / "20260411160000.md",
            folder / "a" / "b" / "c" / "20260414000000.md",
            folder / "drafts.md" / "20260413000000.md",
            folder / "sub" / "20260412090000.md",
        ]

    def test_skips_symlinks_that_resolve_outside_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        kept = tx_notes.write(tx_notes.concept(), "20260411145300")
        private = tx_notes.write(tx_notes.concept("20260101000000", "Private"), "private", paths.zettelkasten)
        (paths.folder / "leak.md").symlink_to(private)
        outside = paths.vault_root.parent / "outside"
        tx_notes.write(tx_notes.plain(), "20260411160000", outside)
        (paths.folder / "outdir").symlink_to(outside, target_is_directory=True)

        assert iter_note_files(paths) == [kept]

    def test_empty_folder_gives_empty_list(self, paths: TiromexPaths) -> None:
        assert iter_note_files(paths) == []

    def test_missing_folder_gives_empty_list(self, tx_vault: TxVault) -> None:
        missing = resolve_tiromex(tx_vault.zettelkasten, "absent")

        assert iter_note_files(missing) == []
        assert not missing.folder.exists()

    def test_lists_only_the_given_folder(self, tx_vault: TxVault, tx_notes: TxNoteBuilder) -> None:
        tx_notes.write(tx_notes.concept(), "20260411145300")
        atlas_note = tx_notes.write(tx_notes.plain(), "20260411160000", tx_vault.zettelkasten / "atlas")
        tx_notes.write(tx_notes.plain("20260411170000", "Loose"), "20260411170000", tx_vault.zettelkasten)

        assert iter_note_files(resolve_tiromex(tx_vault.zettelkasten, "atlas")) == [atlas_note]


class TestTxStateDir:
    def test_uses_xdg_state_home(self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch) -> None:
        assert tx_state_dir() == tx_vault.state_home / "bim" / "tx"

        other = tx_vault.root.parent / "other-state"
        monkeypatch.setenv("XDG_STATE_HOME", str(other))

        assert tx_state_dir() == other / "bim" / "tx"

    def test_falls_back_to_home_local_state(self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_STATE_HOME")

        assert tx_state_dir() == tx_vault.home / ".local" / "state" / "bim" / "tx"

        other_home = tx_vault.root.parent / "other-home"
        monkeypatch.setenv("HOME", str(other_home))

        assert tx_state_dir() == other_home / ".local" / "state" / "bim" / "tx"

    @pytest.mark.parametrize("value", ["", "rel/state"])
    def test_empty_or_relative_xdg_state_home_falls_back_to_home(
        self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.chdir(tx_vault.root)
        monkeypatch.setenv("XDG_STATE_HOME", value)

        assert tx_state_dir() == tx_vault.home / ".local" / "state" / "bim" / "tx"


def _write_state(state_home: Path, content: str | bytes) -> Path:
    state_file = state_home / "bim" / "tx" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        state_file.write_bytes(content)
    else:
        state_file.write_text(content, encoding="utf-8")
    return state_file


class TestReadLastMaintain:
    @pytest.mark.parametrize("stamp", ["2026-11-01T10:00:00+00:00", "2026-10-20T08:30:00+02:00"])
    def test_returns_last_maintain_string(self, tx_vault: TxVault, stamp: str) -> None:
        _write_state(tx_vault.state_home, f'{{"pending": 2, "last_maintain": "{stamp}"}}')

        assert read_last_maintain() == stamp

    def test_returns_empty_string_as_written(self, tx_vault: TxVault) -> None:
        _write_state(tx_vault.state_home, '{"last_maintain": ""}')

        assert read_last_maintain() == ""

    def test_missing_state_file_gives_none(self) -> None:
        assert read_last_maintain() is None

    @pytest.mark.parametrize(
        "content",
        [
            "",
            "{not json",
            "[]",
            '["last_maintain"]',
            '"2026-11-01T10:00:00+00:00"',
            "{}",
            '{"last_maintained": "2026-11-01T10:00:00+00:00"}',
            '{"last_maintain": 20261101}',
            '{"last_maintain": null}',
            '{"last_maintain": ["2026-11-01T10:00:00+00:00"]}',
            b'{"last_maintain": "\xff\xfe"}',
        ],
    )
    def test_unusable_state_gives_none(self, tx_vault: TxVault, content: str | bytes) -> None:
        _write_state(tx_vault.state_home, content)

        assert read_last_maintain() is None

    def test_unreadable_state_path_gives_none(self, tx_vault: TxVault) -> None:
        (tx_vault.state_home / "bim" / "tx" / "state.json").mkdir(parents=True)

        assert read_last_maintain() is None

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads mode-000 files")
    def test_permission_denied_state_file_gives_none(self, tx_vault: TxVault) -> None:
        state_file = _write_state(tx_vault.state_home, '{"last_maintain": "2026-11-01T10:00:00+00:00"}')
        state_file.chmod(0o000)
        try:
            assert read_last_maintain() is None
        finally:
            state_file.chmod(0o600)

    def test_reads_from_current_xdg_state_home(self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch) -> None:
        other = tx_vault.root.parent / "other-state"
        _write_state(tx_vault.state_home, '{"last_maintain": "2026-11-01T10:00:00+00:00"}')
        _write_state(other, '{"last_maintain": "2026-09-09T09:09:09+00:00"}')

        assert read_last_maintain() == "2026-11-01T10:00:00+00:00"
        monkeypatch.setenv("XDG_STATE_HOME", str(other))
        assert read_last_maintain() == "2026-09-09T09:09:09+00:00"


class TestGetTiromexPaths:
    def test_builds_paths_from_settings(self, tx_vault: TxVault) -> None:
        assert get_tiromex_paths(BimSettings()) == TiromexPaths(
            vault_root=tx_vault.root,
            zettelkasten=tx_vault.zettelkasten,
            folder=tx_vault.folder,
        )

    def test_follows_the_settings_argument_not_the_environment(
        self, tx_vault: TxVault, other_vault: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BUVIS_BIM_TIROMEX_FOLDER", "atlas")
        (tx_vault.home / "kb" / "notes").mkdir(parents=True)
        settings = BimSettings.model_validate({"path_zettelkasten": str(other_vault), "tiromex_folder": "tx"})
        home_settings = BimSettings.model_validate({"path_zettelkasten": "~/kb/notes", "tiromex_folder": "inbox"})

        assert get_tiromex_paths(settings) == TiromexPaths(
            vault_root=other_vault.parent,
            zettelkasten=other_vault,
            folder=other_vault / "tx",
        )
        assert get_tiromex_paths(home_settings) == TiromexPaths(
            vault_root=tx_vault.home / "kb",
            zettelkasten=tx_vault.home / "kb" / "notes",
            folder=tx_vault.home / "kb" / "notes" / "inbox",
        )

    def test_honours_tiromex_folder_setting(self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_BIM_TIROMEX_FOLDER", "atlas")

        assert get_tiromex_paths(BimSettings()).folder == tx_vault.zettelkasten / "atlas"

    def test_expands_user_in_path_zettelkasten(self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch) -> None:
        (tx_vault.home / "kb" / "notes").mkdir(parents=True)
        monkeypatch.setenv("BUVIS_BIM_PATH_ZETTELKASTEN", "~/kb/notes")

        result = get_tiromex_paths(BimSettings())

        assert result.zettelkasten == tx_vault.home / "kb" / "notes"
        assert result.vault_root == tx_vault.home / "kb"
        assert result.folder == tx_vault.home / "kb" / "notes" / "tiromex"

    def test_surfaces_bad_folder_setting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_BIM_TIROMEX_FOLDER", "../tiromex")

        with pytest.raises(ValueError):
            get_tiromex_paths(BimSettings())

    def test_surfaces_missing_zettelkasten(self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_BIM_PATH_ZETTELKASTEN", str(tx_vault.root / "absent"))

        with pytest.raises(ValueError):
            get_tiromex_paths(BimSettings())


class TestPlainNoteValidation:
    def test_plain_note_validates_with_base_fields_only(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        from bim.commands.tx.shared.validator import validate_tiromex

        loose = (
            "---\nid: 20260411160000\ntitle: Errands\ndate: 2026-01-01T00:00:00+00:00\ntype: note\n"
            'publish: true\ntags: [person, "topic:x"]\n---\n\nNo heading.\n# One\n# Two\n'
        )
        tx_notes.write(loose, "groceries")
        tx_notes.write(tx_notes.plain("20260411170000", "Todo").replace('title: "Todo"', 'title: ""'), "20260411170000")
        tx_notes.write(tx_notes.plain().replace("type: note\n", ""), "20260411180000", paths.folder / "sub")

        assert [(d.path, d.rule) for d in validate_tiromex(paths)] == [
            ("notes/tiromex/20260411170000.md", "required-field"),
            ("notes/tiromex/sub/20260411180000.md", "required-field"),
        ]


_OUTSIDE_STATEMENT = "Outside claim must stay private"


def _write_outside_notes(vault: TxVault, tx_notes: TxNoteBuilder) -> list[Path]:
    """Write claim-bearing notes under the vault root but outside the tiromex folder."""
    private = tx_notes.concept("20260101000000", "Private", claims=[("c1", _OUTSIDE_STATEMENT)])
    outside = [
        tx_notes.write(private, "private", vault.zettelkasten),
        tx_notes.write(private, "20260101000001", vault.zettelkasten / "tiromex-old"),
        tx_notes.write(private, "20260101000002", vault.root),
    ]
    (vault.folder / "leak.md").symlink_to(outside[0])
    return outside


def _spy_on_reads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record the resolved path of every file opened through Path or builtins.open."""
    opened: list[Path] = []
    real = {name: getattr(Path, name) for name in ("read_text", "read_bytes", "open")}
    real_open = builtins.open

    def record(file: object) -> None:
        if isinstance(file, (str, bytes, os.PathLike)):
            opened.append(Path(os.fsdecode(file)).resolve())

    def wrap(name: str) -> Any:
        def spy(self: Path, *args: Any, **kwargs: Any) -> Any:
            record(self)
            return real[name](self, *args, **kwargs)

        return spy

    def spy_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        record(file)
        return real_open(file, *args, **kwargs)

    for name in real:
        monkeypatch.setattr(Path, name, wrap(name))
    monkeypatch.setattr(builtins, "open", spy_open)
    return opened


class TestOutsideNotesAreNeverRead:
    def test_validate_export_and_status_never_open_a_vault_note_outside_the_folder(
        self, paths: TiromexPaths, tx_vault: TxVault, tx_notes: TxNoteBuilder
    ) -> None:
        inside = tx_notes.write(
            tx_notes.concept(
                claims=[("c1", "Inside claim holds")], backmatter=["- supports:: [[notes/private|Private]]"]
            ),
            "20260411145300",
        )
        tx_notes.write(tx_notes.index(), "20260411140000")
        outside = _write_outside_notes(tx_vault, tx_notes)
        before = {file: file.read_bytes() for file in outside}

        with pytest.MonkeyPatch.context() as patcher:
            opened = _spy_on_reads(patcher)
            CommandTxValidate(paths).execute()
            exported = CommandTxExportClaims(paths).execute()
            CommandTxStatus(paths).execute()

        leaked = [
            file for file in opened if file.is_relative_to(tx_vault.root) and not file.is_relative_to(paths.folder)
        ]
        assert leaked == []
        assert inside in opened
        assert exported.success is True
        assert "Inside claim holds" in exported.output
        assert _OUTSIDE_STATEMENT not in exported.output
        claims = json.dumps(collect_claims([read_note(paths, file) for file in iter_note_files(paths)]))
        assert "Inside claim holds" in claims
        assert _OUTSIDE_STATEMENT not in claims
        assert {file: file.read_bytes() for file in outside} == before
