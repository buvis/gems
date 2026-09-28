"""CLI tests for ``bim doc migrate-layout`` (PRD 00056).

Mirrors the ``test_cli_audit`` patching style: ``get_settings`` is patched to
supply a fully-formed ``BimSettings`` and the doc-subsystem factories are
patched to keep the test off the network and off pdfminer.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import patch

from bim.cli import cli
from bim.commands.doc.migrate.migrate_layout import MigrateServices
from bim.commands.doc.shared.settings_models import DocPaths, DocSettings
from bim.settings import BimSettings
from click.testing import CliRunner

_VAULT_SUBDIR = "Zettelkasten/documents"


def _bim_settings_with_doc(tmp_path: Path) -> BimSettings:
    return BimSettings(
        path_zettelkasten=str(tmp_path / "zk"),
        path_archive=str(tmp_path / "archive"),
        doc=DocSettings(
            paths=DocPaths.model_validate(
                {
                    "business_root": str(tmp_path / "Business"),
                    "vault_root": str(tmp_path / "Vault"),
                    "state_dir": str(tmp_path / "state"),
                    "issuers_file": str(tmp_path / "issuers.yml"),
                }
            ),
        ),
    )


def _patches(settings: BimSettings, services: MigrateServices) -> list:
    return [
        patch("bim.doc_cli.get_settings", return_value=settings),
        patch("bim.dependencies.get_health_checker", return_value=lambda _s: None),
        patch("bim.dependencies.get_migrate_services", return_value=services),
    ]


class TestBimDocMigrateLayoutHelp:
    def test_help_lists_command(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["doc", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "migrate-layout" in result.output

    def test_command_help_shows_apply_and_dry_run(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["doc", "migrate-layout", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "--apply" in result.output
        assert "dry run" in result.output.lower()


class TestBimDocMigrateLayout:
    def _write_legacy(self, tmp_path: Path) -> Path:
        base_dir = tmp_path / "Vault" / _VAULT_SUBDIR
        base_dir.mkdir(parents=True, exist_ok=True)
        pdf = tmp_path / "Business" / "cez-as" / "x.invoice.pdf"
        legacy = base_dir / "x.invoice.md"
        legacy.write_text(
            f'---\ntitle: t\ntype: document\nfile-path: "[Open file](file://{pdf})"\n---\n\n# t\n',
            encoding="utf-8",
        )
        return legacy

    def test_dry_run_default_changes_nothing(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        legacy = self._write_legacy(tmp_path)
        services = MigrateServices(
            legacy_zettels=(str(legacy),),
            vault_root=tmp_path / "Vault",
            vault_documents_subdir=_VAULT_SUBDIR,
        )
        with contextlib.ExitStack() as stack:
            for ctx in _patches(settings, services):
                stack.enter_context(ctx)
            result = runner.invoke(cli, ["doc", "migrate-layout"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert legacy.is_file()
        assert not (tmp_path / "Vault" / _VAULT_SUBDIR / "cez-as" / "x.invoice.md").exists()

    def test_apply_performs_move(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        legacy = self._write_legacy(tmp_path)
        services = MigrateServices(
            legacy_zettels=(str(legacy),),
            vault_root=tmp_path / "Vault",
            vault_documents_subdir=_VAULT_SUBDIR,
        )
        with contextlib.ExitStack() as stack:
            for ctx in _patches(settings, services):
                stack.enter_context(ctx)
            result = runner.invoke(cli, ["doc", "migrate-layout", "--apply"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "migrated 1" in result.output
        assert (tmp_path / "Vault" / _VAULT_SUBDIR / "cez-as" / "x.invoice.md").is_file()
        assert not legacy.exists()

    def test_panics_when_doc_section_missing(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = BimSettings(
            path_zettelkasten=str(tmp_path / "zk"),
            path_archive=str(tmp_path / "archive"),
        )
        with patch("bim.doc_cli.get_settings", return_value=settings):
            result = runner.invoke(cli, ["doc", "migrate-layout"], catch_exceptions=True)
        assert result.exit_code != 0 or "[doc] section missing" in result.output


class TestMigrateLayoutClearsAudit:
    """After apply, a fresh audit no longer reports the migrated zettel as legacy."""

    def test_post_migration_audit_has_no_legacy_entry(self, runner: CliRunner, tmp_path: Path) -> None:
        from datetime import datetime, timezone

        from bim.commands.doc.audit.auditor import Auditor
        from bim.commands.doc.migrate.migrate_layout import CommandMigrateLayout, MigrateServices

        business_root = tmp_path / "Business"
        vault_root = tmp_path / "Vault"
        base_dir = vault_root / _VAULT_SUBDIR
        issuer_dir = business_root / "cez-as"
        issuer_dir.mkdir(parents=True)
        # canonical PDF
        pdf = issuer_dir / "20210311000000-cez-as-x.invoice.pdf"
        pdf.write_bytes(b"%PDF-1.4 stub")
        # legacy flat zettel pointing at that PDF
        base_dir.mkdir(parents=True)
        legacy = base_dir / "20210311000000-cez-as-x.invoice.md"
        legacy.write_text(
            f'---\ntitle: t\ntype: document\nfile-path: "[Open file](file://{pdf})"\n---\n\n# t\n',
            encoding="utf-8",
        )

        registry_path = tmp_path / "issuers.yml"
        registry_path.write_text("doc_types:\n- invoice\nissuers: {}\n", encoding="utf-8")

        # A minimal state_db stub: the auditor only calls get_rule_last_matches()
        # and dedup(sha).is_duplicate. Using a stub avoids sqlite, which cannot
        # open a DB file under this sandbox's scratch tmp path.
        class _DedupResult:
            is_duplicate = True

        class _StubStateDB:
            def get_rule_last_matches(self) -> dict[str, object]:
                return {}

            def dedup(self, _sha: str) -> _DedupResult:
                return _DedupResult()

        state_db = _StubStateDB()

        def _ocr_reader(_p: Path) -> tuple[bool, float | None]:
            return (True, None)

        def _hash_reader(_p: Path) -> str:
            return "0" * 64

        auditor = Auditor(
            state_db=state_db,
            business_root=business_root,
            vault_root=vault_root,
            vault_documents_subdir=_VAULT_SUBDIR,
            low_confidence_threshold=0.7,
            ocr_quality_reader=_ocr_reader,
            hash_reader=_hash_reader,
            now_provider=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        before = auditor.run(registry_path)
        assert str(legacy) in before.legacy_layout_zettels

        cmd = CommandMigrateLayout(
            services=MigrateServices(
                legacy_zettels=before.legacy_layout_zettels,
                vault_root=vault_root,
                vault_documents_subdir=_VAULT_SUBDIR,
            ),
            dry_run=False,
        )
        assert cmd.execute().metadata["migrated_count"] == 1

        after = auditor.run(registry_path)
        assert str(legacy) not in after.legacy_layout_zettels
        assert (base_dir / "cez-as" / "20210311000000-cez-as-x.invoice.md").is_file()
