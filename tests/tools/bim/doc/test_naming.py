from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from bim.commands.doc.shared.naming import (
    CANONICAL_REGEX,
    build_canonical_filename,
    resolve_collision,
    slugify,
)
from pytest_mock import MockerFixture


def _advance_seconds(zk_timestamp: str, seconds: int) -> str:
    moment = datetime.strptime(zk_timestamp, "%Y%m%d%H%M%S")
    return (moment + timedelta(seconds=seconds)).strftime("%Y%m%d%H%M%S")


class TestSlugify:
    def test_diacritics_transliterated(self) -> None:
        assert slugify("ČEZ") == "cez"

    def test_full_company_name(self) -> None:
        assert slugify("Plzeňský Prazdroj, a.s.") == "plzensky-prazdroj-a-s"

    def test_collapses_repeated_separators(self) -> None:
        assert slugify("foo   bar___baz") == "foo-bar-baz"

    def test_strips_leading_and_trailing_hyphens(self) -> None:
        assert slugify("--foo--") == "foo"

    def test_idempotent(self) -> None:
        once = slugify("ČEZ Prodej")
        assert slugify(once) == once

    def test_lowercases(self) -> None:
        assert slugify("MixedCase") == "mixedcase"

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError):
            slugify("")

    def test_only_punctuation_raises(self) -> None:
        with pytest.raises(ValueError):
            slugify("---")


class TestBuildCanonicalFilename:
    def test_prd_example(self) -> None:
        result = build_canonical_filename(
            zk_timestamp="20210311083422",
            issuer_slug="cez-as",
            title_or_number="7102105594",
            doc_type="invoice",
            ext="pdf",
        )
        assert result == "20210311083422-cez-as-7102105594.invoice.pdf"
        assert CANONICAL_REGEX.match(result)

    def test_default_ext_pdf(self) -> None:
        result = build_canonical_filename(
            zk_timestamp="20210311083422",
            issuer_slug="cez-as",
            title_or_number="7102105594",
            doc_type="invoice",
        )
        assert result.endswith(".invoice.pdf")

    def test_re_slugifies_title(self) -> None:
        result = build_canonical_filename(
            zk_timestamp="20210311083422",
            issuer_slug="cez-as",
            title_or_number="2021 Q1 Statement",
            doc_type="statement",
        )
        assert result == "20210311083422-cez-as-2021-q1-statement.statement.pdf"

    def test_invalid_zk_timestamp_too_short(self) -> None:
        with pytest.raises(ValueError):
            build_canonical_filename(
                zk_timestamp="2021031108342",
                issuer_slug="cez-as",
                title_or_number="x",
                doc_type="invoice",
            )

    def test_invalid_zk_timestamp_non_digit(self) -> None:
        with pytest.raises(ValueError):
            build_canonical_filename(
                zk_timestamp="2021031108342X",
                issuer_slug="cez-as",
                title_or_number="x",
                doc_type="invoice",
            )

    def test_uppercase_issuer_slug_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_canonical_filename(
                zk_timestamp="20210311083422",
                issuer_slug="CEZ-AS",
                title_or_number="x",
                doc_type="invoice",
            )

    def test_unknown_doc_type_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_canonical_filename(
                zk_timestamp="20210311083422",
                issuer_slug="cez-as",
                title_or_number="x",
                doc_type="bogus",
            )

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValueError, match="title_or_number must be non-empty"):
            build_canonical_filename(
                zk_timestamp="20210311083422",
                issuer_slug="cez-as",
                title_or_number="",
                doc_type="invoice",
            )

    def test_whitespace_only_title_rejected(self) -> None:
        with pytest.raises(ValueError, match="title_or_number must be non-empty"):
            build_canonical_filename(
                zk_timestamp="20210311083422",
                issuer_slug="cez-as",
                title_or_number="   ",
                doc_type="invoice",
            )


class TestCanonicalRegex:
    def test_matches_example(self) -> None:
        assert CANONICAL_REGEX.match("20210311083422-cez-as-7102105594.invoice.pdf")

    def test_rejects_uppercase(self) -> None:
        assert not CANONICAL_REGEX.match("20210311083422-CEZ-as-7102105594.invoice.pdf")

    def test_rejects_short_timestamp(self) -> None:
        assert not CANONICAL_REGEX.match("2021031108342-cez-as-7102105594.invoice.pdf")

    def test_rejects_unknown_doc_type(self) -> None:
        assert not CANONICAL_REGEX.match("20210311083422-cez-as-7102105594.bogus.pdf")


class TestLazyUnidecodeImport:
    """naming.py must be loadable without the unidecode package installed
    (so consumers outside the [doc] extra don't blow up on import)."""

    def test_module_imports_without_unidecode_at_module_load(self, mocker: MockerFixture) -> None:
        import builtins
        import importlib
        import sys

        original = sys.modules.get("bim.commands.doc.shared.naming")
        try:
            sys.modules.pop("bim.commands.doc.shared.naming", None)
            real_import = builtins.__import__

            def fake_import(
                name: str,
                globals_: object = None,
                locals_: object = None,
                fromlist: tuple[str, ...] = (),
                level: int = 0,
            ) -> object:
                if name == "unidecode":
                    raise ModuleNotFoundError("unidecode pretend-missing")
                return real_import(name, globals_, locals_, fromlist, level)

            mocker.patch("builtins.__import__", side_effect=fake_import)
            importlib.import_module("bim.commands.doc.shared.naming")
        finally:
            if original is not None:
                sys.modules["bim.commands.doc.shared.naming"] = original


class TestResolveCollision:
    def test_no_collision_returns_first_candidate_and_creates_target_dir(self, tmp_path: Path) -> None:
        business_root = tmp_path / "business"
        vault_dir = tmp_path / "vault"
        zk_timestamp = "20210311083422"
        issuer_slug = "cez-as"
        title_or_number = "7102105594"
        doc_type = "invoice"

        canonical_filename, resolved_zk_timestamp, target_pdf = resolve_collision(
            zk_timestamp=zk_timestamp,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
            business_root=business_root,
            vault_dir=vault_dir,
        )

        expected_filename = build_canonical_filename(
            zk_timestamp=zk_timestamp,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
        )
        assert canonical_filename == expected_filename
        assert resolved_zk_timestamp == zk_timestamp
        assert target_pdf == business_root / issuer_slug / expected_filename
        assert target_pdf.parent.is_dir()

    def test_one_pdf_collision_advances_timestamp_by_one_second(self, tmp_path: Path) -> None:
        business_root = tmp_path / "business"
        vault_dir = tmp_path / "vault"
        zk_timestamp = "20210311083422"
        issuer_slug = "cez-as"
        title_or_number = "7102105594"
        doc_type = "invoice"

        colliding_filename = build_canonical_filename(
            zk_timestamp=zk_timestamp,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
        )
        colliding_pdf = business_root / issuer_slug / colliding_filename
        colliding_pdf.parent.mkdir(parents=True)
        colliding_pdf.write_bytes(b"existing pdf")

        canonical_filename, resolved_zk_timestamp, target_pdf = resolve_collision(
            zk_timestamp=zk_timestamp,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
            business_root=business_root,
            vault_dir=vault_dir,
        )

        expected_ts = _advance_seconds(zk_timestamp, 1)
        expected_filename = build_canonical_filename(
            zk_timestamp=expected_ts,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
        )
        assert resolved_zk_timestamp == expected_ts
        assert canonical_filename == expected_filename
        assert target_pdf == business_root / issuer_slug / expected_filename

    def test_zettel_only_collision_still_advances_timestamp(self, tmp_path: Path) -> None:
        business_root = tmp_path / "business"
        vault_dir = tmp_path / "vault"
        zk_timestamp = "20210311083422"
        issuer_slug = "cez-as"
        title_or_number = "7102105594"
        doc_type = "invoice"

        colliding_filename = build_canonical_filename(
            zk_timestamp=zk_timestamp,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
        )
        colliding_zettel = vault_dir / issuer_slug / (colliding_filename.removesuffix(".pdf") + ".md")
        colliding_zettel.parent.mkdir(parents=True)
        colliding_zettel.write_text("existing zettel")

        canonical_filename, resolved_zk_timestamp, target_pdf = resolve_collision(
            zk_timestamp=zk_timestamp,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
            business_root=business_root,
            vault_dir=vault_dir,
        )

        expected_ts = _advance_seconds(zk_timestamp, 1)
        expected_filename = build_canonical_filename(
            zk_timestamp=expected_ts,
            issuer_slug=issuer_slug,
            title_or_number=title_or_number,
            doc_type=doc_type,
        )
        assert resolved_zk_timestamp == expected_ts
        assert canonical_filename == expected_filename
        assert target_pdf == business_root / issuer_slug / expected_filename

    def test_sixty_consecutive_collisions_raises_value_error(self, tmp_path: Path) -> None:
        business_root = tmp_path / "business"
        vault_dir = tmp_path / "vault"
        zk_timestamp = "20210311083422"
        issuer_slug = "cez-as"
        title_or_number = "7102105594"
        doc_type = "invoice"

        issuer_dir = business_root / issuer_slug
        issuer_dir.mkdir(parents=True)
        for offset in range(60):
            candidate_ts = _advance_seconds(zk_timestamp, offset)
            candidate_filename = build_canonical_filename(
                zk_timestamp=candidate_ts,
                issuer_slug=issuer_slug,
                title_or_number=title_or_number,
                doc_type=doc_type,
            )
            (issuer_dir / candidate_filename).write_bytes(b"existing pdf")

        with pytest.raises(ValueError, match=r"could not resolve filename collision after 60 attempts"):
            resolve_collision(
                zk_timestamp=zk_timestamp,
                issuer_slug=issuer_slug,
                title_or_number=title_or_number,
                doc_type=doc_type,
                business_root=business_root,
                vault_dir=vault_dir,
            )
