from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from bim.commands.doc.shared.zettel_helpers import (
    build_zettel_tags,
    compose_zettel_title,
    to_tilde_path,
)


class TestToTildePath:
    def test_path_under_home_returns_tilde_relative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin Path.home() so the test is reproducible across machines.
        fake_home = Path("/Users/test")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        result = to_tilde_path(fake_home / "Library" / "Mobile Documents" / "x.pdf")
        assert result == "~/Library/Mobile Documents/x.pdf"

    def test_path_outside_home_keeps_tilde_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_home = Path("/Users/test")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        result = to_tilde_path(Path("/var/tmp/x.pdf"))
        # The validator only requires `~/` prefix; the synthetic form preserves the absolute path.
        assert result.startswith("~/")
        assert result == "~/var/tmp/x.pdf"


class TestBuildZettelTags:
    def test_full_tags_with_date(self) -> None:
        tags = build_zettel_tags("invoice", "cez-as", date(2021, 3, 11))
        assert tags == ["document/invoice", "issuer/cez-as", "year/2021"]

    def test_tags_without_date(self) -> None:
        tags = build_zettel_tags("invoice", "cez-as", None)
        assert tags == ["document/invoice", "issuer/cez-as"]

    def test_tags_drop_empty_issuer_slug(self) -> None:
        # Triage path may have an unresolved issuer; tag list should still be valid.
        tags = build_zettel_tags("other", "", date(2021, 1, 1))
        assert tags == ["document/other", "year/2021"]


class TestComposeZettelTitle:
    def test_doc_number_truthy_uses_number_branch(self) -> None:
        assert compose_zettel_title("ČEZ a.s.", "invoice", "7102105594", None) == "ČEZ a.s. invoice 7102105594"

    def test_doc_number_truthy_takes_precedence_over_doc_title(self) -> None:
        # When both are present, doc_number wins per spec.
        assert compose_zettel_title("ČEZ a.s.", "invoice", "7102105594", "Some Title") == "ČEZ a.s. invoice 7102105594"

    def test_doc_title_fallback_when_doc_number_none(self) -> None:
        assert (
            compose_zettel_title("ČEZ a.s.", "contract", None, "Energy Supply Agreement")
            == "ČEZ a.s. contract Energy Supply Agreement"
        )

    def test_doc_title_fallback_when_doc_number_empty_string(self) -> None:
        # Empty string is falsy; helper should fall back to title.
        assert compose_zettel_title("Acme", "other", "", "Some Memo") == "Acme other Some Memo"

    def test_both_empty_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="title needs doc_number or doc_title"):
            compose_zettel_title("ČEZ a.s.", "invoice", None, None)

    def test_both_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="title needs doc_number or doc_title"):
            compose_zettel_title("ČEZ a.s.", "invoice", "", "")

    def test_doc_type_casing_preserved(self) -> None:
        # Spec example uses lowercase 'invoice'; helper must not capitalise.
        result = compose_zettel_title("Foo", "invoice", "1", None)
        assert "invoice" in result
        assert "Invoice" not in result

    def test_whitespace_collapsed_in_inputs(self) -> None:
        # Embedded line breaks, tabs, and runs of spaces collapse to single spaces.
        assert (
            compose_zettel_title("  ČEZ\n a.s.  ", "invoice", "  710\t2105594  ", None)
            == "ČEZ a.s. invoice 710 2105594"
        )

    def test_whitespace_collapse_in_doc_title_branch(self) -> None:
        assert (
            compose_zettel_title("Acme", "other", None, "  Memo  about\n  pricing  ") == "Acme other Memo about pricing"
        )

    def test_unicode_preserved(self) -> None:
        # Slovak / Czech characters must round-trip — helper does no slugification.
        assert compose_zettel_title("ČEZ", "invoice", "ABC-123", None) == "ČEZ invoice ABC-123"
