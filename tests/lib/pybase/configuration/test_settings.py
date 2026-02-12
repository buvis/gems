"""Tests for ToolSettings base model."""

from __future__ import annotations

import pytest
from buvis.pybase.configuration.settings import ToolSettings
from pydantic import ValidationError


class TestToolSettings:
    def test_defaults(self) -> None:
        settings = ToolSettings()

        assert settings.enabled is True

    def test_immutable(self) -> None:
        settings = ToolSettings()

        with pytest.raises(ValidationError):
            settings.enabled = False

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            ToolSettings(unknown_field=True)
