"""Unit tests for the shared validators module.

The validator is exercised indirectly through Pydantic field validators on
``ProcessedRow.sha256`` and ``TriageProposal.source.sha256``. These tests
cover the contract directly so future callers that bypass Pydantic still
get the regex contract documented and pinned.
"""

from __future__ import annotations

import hashlib

import pytest
from bim.commands.doc.shared.validators import (
    SHA256_HEX64_REGEX,
    validate_sha256_hex64,
)

VALID_HEX64 = hashlib.sha256(b"abc").hexdigest()
# = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class TestValidateSha256Hex64Accepts:
    def test_valid_lowercase_hex_returns_unchanged(self) -> None:
        assert validate_sha256_hex64("sha256", VALID_HEX64) == VALID_HEX64

    def test_all_zeros(self) -> None:
        sha = "0" * 64
        assert validate_sha256_hex64("sha256", sha) == sha

    def test_all_fs(self) -> None:
        sha = "f" * 64
        assert validate_sha256_hex64("sha256", sha) == sha


class TestValidateSha256Hex64Rejects:
    def test_empty_string(self) -> None:
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", "")

    def test_one_char_short(self) -> None:
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", "a" * 63)

    def test_one_char_long(self) -> None:
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", "a" * 65)

    def test_uppercase_hex(self) -> None:
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", "A" * 64)

    def test_mixed_case_hex(self) -> None:
        # First char uppercase, rest lowercase — regex anchors require all-lower.
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", "A" + VALID_HEX64[1:])

    def test_non_hex_char_g(self) -> None:
        # 'g' is one past the hex range; substituting it must fail.
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", "g" * 64)

    def test_leading_whitespace(self) -> None:
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", " " + VALID_HEX64[1:])

    def test_trailing_whitespace(self) -> None:
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", VALID_HEX64[:-1] + " ")

    def test_internal_whitespace(self) -> None:
        # Replace one hex char with space, keep length 64.
        with pytest.raises(ValueError):
            validate_sha256_hex64("sha256", VALID_HEX64[:32] + " " + VALID_HEX64[33:])


class TestValidateSha256Hex64ErrorMessage:
    def test_error_message_includes_field_label(self) -> None:
        with pytest.raises(ValueError, match="file_sha256"):
            validate_sha256_hex64("file_sha256", "not-a-hash")

    def test_error_message_includes_offending_value(self) -> None:
        with pytest.raises(ValueError, match="bogus"):
            validate_sha256_hex64("sha256", "bogus")


class TestSha256Hex64Regex:
    def test_regex_anchored_at_both_ends(self) -> None:
        # A 64-char lowercase hex with extra suffix must NOT match — confirms
        # the regex uses ^...$ anchors so substring matches are rejected.
        assert SHA256_HEX64_REGEX.match(VALID_HEX64 + "extra") is None

    def test_regex_matches_known_valid_digest(self) -> None:
        assert SHA256_HEX64_REGEX.match(VALID_HEX64) is not None
