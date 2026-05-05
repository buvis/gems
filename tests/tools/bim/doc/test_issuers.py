from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from bim.commands.doc.shared.issuers import (
    IssuerRegistry,
    load_registry,
    register_issuer,
    resolve_alias,
)
from pydantic import ValidationError

FIXTURES = Path(__file__).parent / "fixtures" / "issuers"


@pytest.fixture
def valid_registry_path(tmp_path: Path) -> Path:
    dest = tmp_path / "issuers.yml"
    shutil.copy(FIXTURES / "valid.yml", dest)
    return dest


@pytest.fixture
def aliases_registry_path(tmp_path: Path) -> Path:
    dest = tmp_path / "issuers.yml"
    shutil.copy(FIXTURES / "with_aliases.yml", dest)
    return dest


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    return tmp_path / "issuers.lock"


class TestLoadRegistry:
    def test_happy_path(self, valid_registry_path: Path) -> None:
        registry = load_registry(valid_registry_path)
        assert isinstance(registry, IssuerRegistry)
        assert registry.version == 1
        assert "cez-as" in registry.issuers
        assert "plzensky-prazdroj" in registry.issuers
        assert "invoice" in registry.doc_types
        assert "_triage" in registry.reserved_slugs

    def test_issuer_slug_matches_dict_key(self, valid_registry_path: Path) -> None:
        registry = load_registry(valid_registry_path)
        assert registry.issuers["cez-as"].slug == "cez-as"


class TestResolveAlias:
    def test_exact_slug_match(self, aliases_registry_path: Path) -> None:
        registry = load_registry(aliases_registry_path)
        assert resolve_alias(registry, "cez-as") == "cez-as"

    def test_diacritic_alias(self, aliases_registry_path: Path) -> None:
        registry = load_registry(aliases_registry_path)
        assert resolve_alias(registry, "ČEZ") == "cez-as"

    def test_diacritic_alias_with_words(self, aliases_registry_path: Path) -> None:
        registry = load_registry(aliases_registry_path)
        assert resolve_alias(registry, "ČEZ Prodej") == "cez-as"

    def test_case_insensitive_match(self, aliases_registry_path: Path) -> None:
        registry = load_registry(aliases_registry_path)
        assert resolve_alias(registry, "Cez") == "cez-as"

    def test_no_match_returns_none(self, aliases_registry_path: Path) -> None:
        registry = load_registry(aliases_registry_path)
        assert resolve_alias(registry, "unknown-vendor") is None


class TestRegisterIssuer:
    def test_happy_path(self, valid_registry_path: Path, lock_path: Path) -> None:
        new_registry = register_issuer(
            valid_registry_path,
            lock_path,
            slug="o2-czech",
            display_name="O2 Czech Republic a.s.",
            aliases=["O2", "o2.cz"],
        )
        assert "o2-czech" in new_registry.issuers
        assert new_registry.issuers["o2-czech"].display_name == "O2 Czech Republic a.s."
        reloaded = load_registry(valid_registry_path)
        assert "o2-czech" in reloaded.issuers
        assert reloaded.issuers["o2-czech"].aliases == ["O2", "o2.cz"]

    def test_reserved_slug_rejected(self, valid_registry_path: Path, lock_path: Path) -> None:
        with pytest.raises(ValueError, match="reserved"):
            register_issuer(
                valid_registry_path,
                lock_path,
                slug="_triage",
                display_name="Bad",
            )

    def test_duplicate_slug_rejected(self, valid_registry_path: Path, lock_path: Path) -> None:
        with pytest.raises(ValueError, match="already registered"):
            register_issuer(
                valid_registry_path,
                lock_path,
                slug="cez-as",
                display_name="CEZ duplicate",
            )

    def test_two_sequential_registers_both_succeed(self, valid_registry_path: Path, lock_path: Path) -> None:
        register_issuer(
            valid_registry_path,
            lock_path,
            slug="o2-czech",
            display_name="O2",
        )
        register_issuer(
            valid_registry_path,
            lock_path,
            slug="t-mobile-cz",
            display_name="T-Mobile",
        )
        reloaded = load_registry(valid_registry_path)
        assert "o2-czech" in reloaded.issuers
        assert "t-mobile-cz" in reloaded.issuers
        assert "cez-as" in reloaded.issuers
        assert "plzensky-prazdroj" in reloaded.issuers

    def test_invalid_slug_with_spaces_rejected(self, valid_registry_path: Path, lock_path: Path) -> None:
        with pytest.raises(ValidationError, match="kebab-case"):
            register_issuer(
                valid_registry_path,
                lock_path,
                slug="bad slug with spaces",
                display_name="Bad",
            )

    def test_invalid_slug_with_diacritics_rejected(self, valid_registry_path: Path, lock_path: Path) -> None:
        with pytest.raises(ValidationError, match="kebab-case"):
            register_issuer(
                valid_registry_path,
                lock_path,
                slug="ČEZ",
                display_name="ČEZ",
            )

    def test_invalid_slug_uppercase_rejected(self, valid_registry_path: Path, lock_path: Path) -> None:
        with pytest.raises(ValidationError, match="kebab-case"):
            register_issuer(
                valid_registry_path,
                lock_path,
                slug="CEZ-AS",
                display_name="CEZ",
            )


class TestRegistryValidation:
    def test_reserved_and_issuers_disjoint_violation_rejected(self) -> None:
        with pytest.raises(ValidationError, match="disjoint"):
            IssuerRegistry.model_validate(
                {
                    "version": 1,
                    "doc_types": ["invoice"],
                    "reserved_slugs": ["unknown"],
                    "issuers": {
                        "unknown": {"slug": "unknown", "display_name": "Bad"},
                    },
                }
            )

    def test_invalid_issuer_slug_in_yaml_rejected(self) -> None:
        with pytest.raises(ValidationError, match="kebab-case"):
            IssuerRegistry.model_validate(
                {
                    "version": 1,
                    "doc_types": ["invoice"],
                    "reserved_slugs": [],
                    "issuers": {
                        "Bad Slug": {"slug": "Bad Slug", "display_name": "Bad"},
                    },
                }
            )


class TestCiphertextDetection:
    def test_ciphertext_file_raises_runtime_error(self, tmp_path: Path) -> None:
        encrypted = tmp_path / "issuers.yml"
        shutil.copy(FIXTURES / "ciphertext.yml", encrypted)
        with pytest.raises(RuntimeError, match="git filter"):
            load_registry(encrypted)
