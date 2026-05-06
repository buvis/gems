from __future__ import annotations

import pytest
from bim.commands.doc.shared.naming import (
    CANONICAL_REGEX,
    build_canonical_filename,
    slugify,
)


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

    def test_module_imports_without_unidecode_at_module_load(self, mocker) -> None:  # type: ignore[no-untyped-def]
        import builtins
        import importlib
        import sys

        original = sys.modules.get("bim.commands.doc.shared.naming")
        try:
            sys.modules.pop("bim.commands.doc.shared.naming", None)
            real_import = builtins.__import__

            def fake_import(name, globals_=None, locals_=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
                if name == "unidecode":
                    raise ModuleNotFoundError("unidecode pretend-missing")
                return real_import(name, globals_, locals_, fromlist, level)

            mocker.patch("builtins.__import__", side_effect=fake_import)
            importlib.import_module("bim.commands.doc.shared.naming")
        finally:
            if original is not None:
                sys.modules["bim.commands.doc.shared.naming"] = original
