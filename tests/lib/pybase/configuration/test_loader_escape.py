"""Tests for escape syntax in ConfigurationLoader."""

from __future__ import annotations

from buvis.pybase.configuration.loader import _ESCAPE_PLACEHOLDER, ConfigurationLoader


class TestEscapeLiterals:
    def test_escapes_single_var(self) -> None:
        result = ConfigurationLoader._escape_literals("$${VAR}")

        assert result == f"{_ESCAPE_PLACEHOLDER}{{VAR}}"

    def test_escapes_multiple_vars(self) -> None:
        result = ConfigurationLoader._escape_literals("$${A} and $${B}")

        assert result == f"{_ESCAPE_PLACEHOLDER}{{A}} and {_ESCAPE_PLACEHOLDER}{{B}}"

    def test_leaves_unescaped_vars_alone(self) -> None:
        result = ConfigurationLoader._escape_literals("${VAR}")

        assert result == "${VAR}"

    def test_mixed_escaped_and_unescaped(self) -> None:
        result = ConfigurationLoader._escape_literals("${REAL} and $${LITERAL}")

        assert result == f"${{REAL}} and {_ESCAPE_PLACEHOLDER}{{LITERAL}}"

    def test_empty_string(self) -> None:
        result = ConfigurationLoader._escape_literals("")

        assert result == ""

    def test_no_vars(self) -> None:
        result = ConfigurationLoader._escape_literals("plain text")

        assert result == "plain text"


class TestRestoreLiterals:
    def test_restores_single_placeholder(self) -> None:
        escaped = f"{_ESCAPE_PLACEHOLDER}{{VAR}}"

        result = ConfigurationLoader._restore_literals(escaped)

        assert result == "${VAR}"

    def test_restores_multiple_placeholders(self) -> None:
        escaped = f"{_ESCAPE_PLACEHOLDER}{{A}} and {_ESCAPE_PLACEHOLDER}{{B}}"

        result = ConfigurationLoader._restore_literals(escaped)

        assert result == "${A} and ${B}"

    def test_empty_string(self) -> None:
        result = ConfigurationLoader._restore_literals("")

        assert result == ""

    def test_no_placeholders(self) -> None:
        result = ConfigurationLoader._restore_literals("plain text")

        assert result == "plain text"


class TestEscapeRoundTrip:
    def test_escape_then_restore_single(self) -> None:
        original = "$${LITERAL_VAR}"

        escaped = ConfigurationLoader._escape_literals(original)
        restored = ConfigurationLoader._restore_literals(escaped)

        assert restored == "${LITERAL_VAR}"

    def test_escape_then_restore_mixed(self) -> None:
        original = "prefix $${ESCAPED} middle ${REAL} suffix"

        escaped = ConfigurationLoader._escape_literals(original)
        # After escaping, ${REAL} is untouched, $${ESCAPED} becomes placeholder
        restored = ConfigurationLoader._restore_literals(escaped)

        assert restored == "prefix ${ESCAPED} middle ${REAL} suffix"

    def test_with_default_syntax(self) -> None:
        original = "$${VAR:-default}"

        escaped = ConfigurationLoader._escape_literals(original)
        restored = ConfigurationLoader._restore_literals(escaped)

        assert restored == "${VAR:-default}"
