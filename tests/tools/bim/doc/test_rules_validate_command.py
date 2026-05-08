"""Tests for the bim doc rules validate command class."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write(path: Path, body: str) -> None:
    path.write_text(body)


class TestRulesValidateOk:
    def test_valid_registry_with_rules(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.validate import CommandRulesValidate

        f = tmp_path / "issuers.yml"
        _write(
            f,
            """
version: 1
doc_types: [invoice, statement]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: CEZ a.s.
    aliases: []
    rules:
      - id: cez-fingerprint
        partial: true
        match: {ocr_contains: ["IC: 45274649"]}
        extract: {issuer_slug: cez-as, issuer_display: CEZ a.s.}
""",
        )
        result = CommandRulesValidate().run(f)
        assert result.success is True
        assert "ok" in (result.output or "").lower()

    def test_registry_with_no_rules_blocks(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.validate import CommandRulesValidate

        f = tmp_path / "issuers.yml"
        _write(
            f,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: CEZ a.s.
    aliases: []
""",
        )
        result = CommandRulesValidate().run(f)
        assert result.success is True


class TestRulesValidateErrors:
    @pytest.fixture
    def issuers_path(self, tmp_path: Path) -> Path:
        return tmp_path / "issuers.yml"

    def test_duplicate_rule_id_across_issuers(self, issuers_path: Path) -> None:
        from bim.commands.doc.rules.validate import CommandRulesValidate

        _write(
            issuers_path,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: CEZ a.s.
    aliases: []
    rules:
      - id: shared-id
        partial: true
        match: {ocr_contains: ["x"]}
        extract: {issuer_slug: cez-as}
  eon-cz:
    display_name: E.ON
    aliases: []
    rules:
      - id: shared-id
        partial: true
        match: {ocr_contains: ["y"]}
        extract: {issuer_slug: eon-cz}
""",
        )
        result = CommandRulesValidate().run(issuers_path)
        assert result.success is False
        message = (result.error or "") + (result.output or "")
        assert "shared-id" in message
        assert "cez-as" in message
        assert "eon-cz" in message

    def test_uncompilable_regex(self, issuers_path: Path) -> None:
        from bim.commands.doc.rules.validate import CommandRulesValidate

        _write(
            issuers_path,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: CEZ a.s.
    aliases: []
    rules:
      - id: bad-regex
        partial: true
        match: {ocr_matches: ["(unclosed-group"]}
        extract: {issuer_slug: cez-as}
""",
        )
        result = CommandRulesValidate().run(issuers_path)
        assert result.success is False
        # Error message must name the offending rule by id (PRD acceptance:
        # "per-error details with rule id and field name").
        assert "bad-regex" in (result.error or "")

    def test_unknown_transform(self, issuers_path: Path) -> None:
        from bim.commands.doc.rules.validate import CommandRulesValidate

        _write(
            issuers_path,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: CEZ a.s.
    aliases: []
    rules:
      - id: bad-transform
        match: {ocr_contains: ["x"]}
        extract:
          doc_amount:
            from: ocr_match
            pattern: "amount: (\\\\d+)"
            group: 1
            transform: nonsense_transform
""",
        )
        result = CommandRulesValidate().run(issuers_path)
        assert result.success is False
        message = (result.error or "") + (result.output or "")
        assert "nonsense_transform" in message or "transform" in message.lower()

    def test_reserved_field_in_extract(self, issuers_path: Path) -> None:
        from bim.commands.doc.rules.validate import CommandRulesValidate

        _write(
            issuers_path,
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: CEZ a.s.
    aliases: []
    rules:
      - id: bad-reserved
        partial: true
        match: {ocr_contains: ["x"]}
        extract:
          file_path: "should not be settable"
""",
        )
        result = CommandRulesValidate().run(issuers_path)
        assert result.success is False

    def test_file_does_not_exist(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.validate import CommandRulesValidate

        result = CommandRulesValidate().run(tmp_path / "missing.yml")
        assert result.success is False
        message = (result.error or "").lower()
        assert "not found" in message or "no such file" in message
