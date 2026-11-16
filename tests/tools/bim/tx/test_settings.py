"""Tests for ``TxSettings`` and the two tiromex fields on ``BimSettings``."""

from __future__ import annotations

from typing import Any

import pytest
from bim.commands.tx.shared.settings import TxSettings
from bim.settings import BimSettings
from pydantic import ValidationError

DEFAULTS: dict[str, Any] = {
    "backend": "claude",
    "max_sources_per_run": 5,
    "source_timeout_seconds": 900,
    "max_zettel_body_lines": 60,
    "maintenance_window_days": 7,
    "pruning_enabled": False,
    "prune_window_days": 365,
    "git_identity_name": "bim-tx",
    "git_identity_email": "bim-tx@localhost",
}

OVERRIDES = [
    ("backend", "codex", "codex"),
    ("backend", "gemini", "gemini"),
    ("max_sources_per_run", "12", 12),
    ("max_sources_per_run", "1", 1),
    ("source_timeout_seconds", "60", 60),
    ("source_timeout_seconds", "1800", 1800),
    ("max_zettel_body_lines", "40", 40),
    ("max_zettel_body_lines", "120", 120),
    ("maintenance_window_days", "3", 3),
    ("maintenance_window_days", "14", 14),
    ("pruning_enabled", "true", True),
    ("pruning_enabled", "0", False),
    ("prune_window_days", "30", 30),
    ("prune_window_days", "730", 730),
    ("git_identity_name", "tx-bot", "tx-bot"),
    ("git_identity_name", "Ada Tx", "Ada Tx"),
    ("git_identity_email", "tx@example.org", "tx@example.org"),
    ("git_identity_email", "bot@vault.test", "bot@vault.test"),
]


class TestDefaults:
    def test_tx_settings_defaults_match_the_contract(self) -> None:
        assert TxSettings().model_dump() == DEFAULTS

    def test_bim_settings_carries_tx_defaults_and_tiromex_folder(self) -> None:
        settings = BimSettings()

        assert settings.tiromex_folder == "tiromex"
        assert isinstance(settings.tx, TxSettings)
        assert settings.tx.model_dump() == DEFAULTS

    def test_path_articles_is_kept(self) -> None:
        assert BimSettings().path_articles == "~/Documents/reference/40-archives/articles/"


class TestEnvOverrides:
    @pytest.mark.parametrize(("field", "raw", "expected"), OVERRIDES)
    def test_each_tx_env_var_overrides_only_its_field(
        self, monkeypatch: pytest.MonkeyPatch, field: str, raw: str, expected: object
    ) -> None:
        monkeypatch.setenv(f"BUVIS_BIM_TX__{field.upper()}", raw)

        settings = BimSettings()

        assert settings.tx.model_dump() == {**DEFAULTS, field: expected}
        assert settings.tiromex_folder == "tiromex"

    def test_several_tx_env_vars_combine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_BIM_TX__MAX_SOURCES_PER_RUN", "8")
        monkeypatch.setenv("BUVIS_BIM_TX__PRUNING_ENABLED", "true")

        tx = BimSettings().tx

        assert tx.max_sources_per_run == 8
        assert tx.pruning_enabled is True
        assert tx.prune_window_days == 365

    @pytest.mark.parametrize("folder", ["atlas", "commonplace"])
    def test_tiromex_folder_env_override(self, monkeypatch: pytest.MonkeyPatch, folder: str) -> None:
        monkeypatch.setenv("BUVIS_BIM_TIROMEX_FOLDER", folder)

        settings = BimSettings()

        assert settings.tiromex_folder == folder
        assert settings.tx.model_dump() == DEFAULTS

    def test_tx_mapping_override(self) -> None:
        settings = BimSettings.model_validate({"tx": {"maintenance_window_days": 2}, "tiromex_folder": "ledger"})

        assert settings.tx.model_dump() == {**DEFAULTS, "maintenance_window_days": 2}
        assert settings.tiromex_folder == "ledger"


class TestRejections:
    def test_unknown_key_rejected_on_tx_settings(self) -> None:
        with pytest.raises(ValidationError, match="model"):
            TxSettings.model_validate({"model": "opus"})

    def test_unknown_key_under_tx_rejected_on_bim_settings(self) -> None:
        with pytest.raises(ValidationError, match="max_sources"):
            BimSettings.model_validate({"tx": {"max_sources": 3}})

    def test_unknown_tx_env_var_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_BIM_TX__BOGUS", "1")

        with pytest.raises(ValidationError, match="bogus"):
            BimSettings()

    def test_non_integer_tx_env_value_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_BIM_TX__MAX_SOURCES_PER_RUN", "many")

        with pytest.raises(ValidationError, match="max_sources_per_run"):
            BimSettings()
