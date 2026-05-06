from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from bim.commands.doc.shared.zettel_helpers import build_zettel_tags, to_tilde_path


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
