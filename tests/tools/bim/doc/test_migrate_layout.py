"""Tests for ``CommandMigrateLayout`` (PRD 00056).

Covers the PRD success criteria:
- dry-run lists the planned moves and changes nothing on disk;
- apply migrates a legacy fixture into its per-issuer subfolder;
- a divergent-frontmatter fixture is skipped-and-reported;
- the ``file-path`` frontmatter link stays valid after migration.
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path

from bim.commands.doc.migrate.migrate_layout import CommandMigrateLayout, MigrateServices

_VAULT_SUBDIR = "Zettelkasten/documents"


def _pdf_link(pdf_path: Path) -> str:
    encoded = urllib.parse.quote(str(pdf_path), safe="/~")
    return f'"[Open file](file://{encoded})"'


def _legacy_zettel(
    base_dir: Path,
    *,
    basename: str,
    issuer_slug: str,
    business_root: Path,
) -> Path:
    """Write a legacy flat-layout zettel and return its path.

    ``file-path`` points at the per-issuer PDF location, so the migrator can
    derive ``issuer_slug`` from it.
    """
    pdf_path = business_root / issuer_slug / f"{basename}.pdf"
    content = (
        "---\n"
        "id: 20210311083422\n"
        "title: Example invoice\n"
        "type: document\n"
        "doc-type: invoice\n"
        f"issuer: {issuer_slug}\n"
        f"file-path: {_pdf_link(pdf_path)}\n"
        "tags:\n"
        "- document/invoice\n"
        "---\n\n"
        "# Example invoice\n\n"
        "## OCR text\n\n"
        "> [!quote]- Full text\n"
        "> body\n"
    )
    legacy = base_dir / f"{basename}.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(content, encoding="utf-8")
    return legacy


def _services(vault_root: Path, legacy: tuple[str, ...]) -> MigrateServices:
    return MigrateServices(
        legacy_zettels=legacy,
        vault_root=vault_root,
        vault_documents_subdir=_VAULT_SUBDIR,
    )


class TestMigrateLayoutDryRun:
    def test_dry_run_lists_plan_and_changes_nothing(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "Vault"
        business_root = tmp_path / "Business"
        base_dir = vault_root / _VAULT_SUBDIR
        legacy = _legacy_zettel(base_dir, basename="x.invoice", issuer_slug="cez-as", business_root=business_root)

        before = legacy.read_text(encoding="utf-8")
        cmd = CommandMigrateLayout(services=_services(vault_root, (str(legacy),)), dry_run=True)
        result = cmd.execute()

        assert result.success
        assert result.metadata["dry_run"] is True
        assert result.metadata["planned_count"] == 1
        assert result.metadata["planned"][0]["issuer_slug"] == "cez-as"
        expected_target = base_dir / "cez-as" / "x.invoice.md"
        assert result.metadata["planned"][0]["target"] == str(expected_target)
        # nothing moved
        assert legacy.is_file()
        assert legacy.read_text(encoding="utf-8") == before
        assert not expected_target.exists()


class TestMigrateLayoutApply:
    def test_apply_migrates_fixture_and_keeps_link_valid(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "Vault"
        business_root = tmp_path / "Business"
        base_dir = vault_root / _VAULT_SUBDIR
        legacy = _legacy_zettel(base_dir, basename="x.invoice", issuer_slug="cez-as", business_root=business_root)
        original_content = legacy.read_text(encoding="utf-8")

        cmd = CommandMigrateLayout(services=_services(vault_root, (str(legacy),)), dry_run=False)
        result = cmd.execute()

        assert result.success
        assert result.metadata["migrated_count"] == 1
        target = base_dir / "cez-as" / "x.invoice.md"
        assert target.is_file()
        assert not legacy.exists()
        # content (including the file-path link) is preserved byte-for-byte
        assert target.read_text(encoding="utf-8") == original_content
        # the PDF link still points at the per-issuer PDF path
        assert "Business/cez-as/x.invoice.pdf" in urllib.parse.unquote(target.read_text(encoding="utf-8"))

    def test_apply_skips_when_target_already_exists(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "Vault"
        business_root = tmp_path / "Business"
        base_dir = vault_root / _VAULT_SUBDIR
        legacy = _legacy_zettel(base_dir, basename="x.invoice", issuer_slug="cez-as", business_root=business_root)
        target = base_dir / "cez-as" / "x.invoice.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("preexisting", encoding="utf-8")

        cmd = CommandMigrateLayout(services=_services(vault_root, (str(legacy),)), dry_run=False)
        result = cmd.execute()

        assert result.success
        assert result.metadata["migrated_count"] == 0
        assert result.metadata["skipped_count"] == 1
        assert "already exists" in result.metadata["skipped"][0]["reason"]
        # legacy untouched, target untouched
        assert legacy.is_file()
        assert target.read_text(encoding="utf-8") == "preexisting"


class TestMigrateLayoutSkip:
    def test_divergent_frontmatter_is_skipped_and_reported(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "Vault"
        base_dir = vault_root / _VAULT_SUBDIR
        base_dir.mkdir(parents=True, exist_ok=True)
        # No file-path key at all -> cannot derive issuer slug -> skip.
        divergent = base_dir / "broken.md"
        divergent.write_text("---\ntitle: broken\ntype: document\n---\n\n# broken\n", encoding="utf-8")

        cmd = CommandMigrateLayout(services=_services(vault_root, (str(divergent),)), dry_run=False)
        result = cmd.execute()

        assert result.success
        assert result.metadata["migrated_count"] == 0
        assert result.metadata["skipped_count"] == 1
        assert "file-path" in result.metadata["skipped"][0]["reason"]
        assert result.warnings  # reported
        assert divergent.is_file()  # never partially migrated

    def test_no_frontmatter_block_is_skipped(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "Vault"
        base_dir = vault_root / _VAULT_SUBDIR
        base_dir.mkdir(parents=True, exist_ok=True)
        plain = base_dir / "plain.md"
        plain.write_text("# just a heading, no frontmatter\n", encoding="utf-8")

        cmd = CommandMigrateLayout(services=_services(vault_root, (str(plain),)), dry_run=False)
        result = cmd.execute()

        assert result.metadata["skipped_count"] == 1
        assert "frontmatter" in result.metadata["skipped"][0]["reason"]

    def test_missing_file_is_skipped(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "Vault"
        missing = vault_root / _VAULT_SUBDIR / "gone.md"
        cmd = CommandMigrateLayout(services=_services(vault_root, (str(missing),)), dry_run=False)
        result = cmd.execute()
        assert result.metadata["skipped_count"] == 1
        assert "not found" in result.metadata["skipped"][0]["reason"]


class TestMigrateLayoutMixed:
    def test_mixed_batch_migrates_valid_and_skips_divergent(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "Vault"
        business_root = tmp_path / "Business"
        base_dir = vault_root / _VAULT_SUBDIR
        good = _legacy_zettel(base_dir, basename="a.invoice", issuer_slug="o2", business_root=business_root)
        bad = base_dir / "bad.md"
        bad.write_text("---\ntitle: bad\n---\n\nbody\n", encoding="utf-8")

        cmd = CommandMigrateLayout(
            services=_services(vault_root, (str(good), str(bad))),
            dry_run=False,
        )
        result = cmd.execute()

        assert result.metadata["migrated_count"] == 1
        assert result.metadata["skipped_count"] == 1
        assert (base_dir / "o2" / "a.invoice.md").is_file()
        assert not good.exists()
        assert bad.is_file()
