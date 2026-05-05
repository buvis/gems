from __future__ import annotations

from pathlib import Path

import pytest
from bim.commands.doc.shared.settings_models import (
    ClassifierSettings,
    DocPaths,
    DocSettings,
    OCRSettings,
    ZettelSettings,
)
from pydantic import ValidationError


@pytest.fixture
def required_paths_data(tmp_path: Path) -> dict[str, str]:
    return {
        "business_root": str(tmp_path / "Business"),
        "vault_root": str(tmp_path / "Vault"),
    }


class TestDocPaths:
    def test_required_business_root_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            DocPaths.model_validate({"vault_root": str(tmp_path / "Vault")})

    def test_required_vault_root_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            DocPaths.model_validate({"business_root": str(tmp_path / "Business")})

    def test_defaults_present_when_only_required_set(
        self,
        required_paths_data: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)
        paths = DocPaths.model_validate(required_paths_data)
        assert paths.vault_documents_subdir == "Zettelkasten/documents"
        assert paths.originals_retention_days == 30
        assert paths.state_dir == Path.home() / ".local" / "state" / "bim" / "doc"

    def test_xdg_state_home_override_used_for_state_dir(
        self,
        required_paths_data: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        xdg = tmp_path / "xdg-state"
        monkeypatch.setenv("XDG_STATE_HOME", str(xdg))
        paths = DocPaths.model_validate(required_paths_data)
        assert paths.state_dir == xdg / "bim" / "doc"

    def test_explicit_state_dir_wins_over_xdg(
        self,
        required_paths_data: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        explicit = tmp_path / "explicit-state"
        data = {**required_paths_data, "state_dir": str(explicit)}
        paths = DocPaths.model_validate(data)
        assert paths.state_dir == explicit

    def test_extra_field_rejected(self, required_paths_data: dict[str, str]) -> None:
        with pytest.raises(ValidationError):
            DocPaths.model_validate({**required_paths_data, "unknown_key": "x"})

    def test_frozen(self, required_paths_data: dict[str, str]) -> None:
        paths = DocPaths.model_validate(required_paths_data)
        with pytest.raises(ValidationError):
            paths.vault_documents_subdir = "other"

    def test_home_monkeypatch_propagates_to_lazy_paths(
        self,
        required_paths_data: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)
        paths = DocPaths.model_validate(required_paths_data)
        assert paths.inbox_downloads is not None
        assert paths.inbox_downloads.is_relative_to(fake_home)
        assert paths.issuers_file is not None
        assert paths.issuers_file.is_relative_to(fake_home)


class TestOCRSettings:
    def test_defaults_match_spec(self) -> None:
        s = OCRSettings()
        assert s.engine == "ocrmypdf"
        assert s.languages == ["ces", "eng"]
        assert s.oversample == 400
        assert s.deskew is True
        assert s.rotate_pages is True
        assert s.redo_on_low_confidence is True
        assert s.low_confidence_threshold == pytest.approx(0.70)
        assert s.skip_text is True

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OCRSettings.model_validate({"unknown_key": 1})


class TestClassifierSettings:
    def test_defaults_match_spec(self) -> None:
        s = ClassifierSettings()
        assert s.backend == "ollama"
        assert s.endpoint == "http://localhost:11434"
        assert s.primary_model == "qwen2.5:7b-instruct"
        assert s.fallback_model == "qwen2.5:14b-instruct"
        assert s.triage_threshold == pytest.approx(0.85)
        assert s.max_retries == 2

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClassifierSettings.model_validate({"unknown_key": 1})


class TestZettelSettings:
    def test_defaults_match_spec(self) -> None:
        s = ZettelSettings()
        assert s.ocr_text_in_body is True
        assert s.ocr_text_collapsible is True
        assert s.ocr_text_max_chars == 0


class TestDocSettings:
    def test_paths_required(self) -> None:
        with pytest.raises(ValidationError):
            DocSettings.model_validate({})

    def test_nested_defaults_present(self, required_paths_data: dict[str, str]) -> None:
        paths = DocPaths.model_validate(required_paths_data)
        settings = DocSettings(paths=paths)
        assert settings.ocr.languages == ["ces", "eng"]
        assert settings.classifier.primary_model == "qwen2.5:7b-instruct"
        assert settings.zettel.ocr_text_in_body is True

    def test_extra_field_rejected(self, required_paths_data: dict[str, str]) -> None:
        paths = DocPaths.model_validate(required_paths_data)
        with pytest.raises(ValidationError):
            DocSettings.model_validate({"paths": paths.model_dump(mode="json"), "unknown_key": 1})
