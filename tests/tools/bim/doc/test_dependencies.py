"""Wiring tests for the bim doc subsystem factories in bim/dependencies.py."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

import pytest
from bim.commands.doc.shared.classifier import Classifier
from bim.commands.doc.shared.extractor import Extractor
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.ocr import OCRRunner
from bim.commands.doc.shared.pipeline import Pipeline, PipelineServices
from bim.commands.doc.shared.settings_models import DocPaths, DocSettings
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.dependencies import _load_issuer_registry, get_pipeline
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository

FIXTURES = Path(__file__).parent / "fixtures" / "issuers"


@pytest.fixture
def doc_settings(tmp_path: Path) -> DocSettings:
    issuers_file = tmp_path / "issuers.yml"
    shutil.copy(FIXTURES / "valid.yml", issuers_file)
    paths = DocPaths.model_validate(
        {
            "business_root": str(tmp_path / "Business"),
            "vault_root": str(tmp_path / "Vault"),
            "state_dir": str(tmp_path / "state"),
            "issuers_file": str(issuers_file),
        }
    )
    return DocSettings(paths=paths)


class TestLoadIssuerRegistry:
    def test_returns_registry_only(self, doc_settings: DocSettings) -> None:
        result = _load_issuer_registry(doc_settings)
        assert isinstance(result, IssuerRegistry)
        assert result.version == 1


class TestGetPipeline:
    def test_wires_all_six_services(self, doc_settings: DocSettings) -> None:
        # ZettelWriter stashes the repo as ``self.repo`` without introspecting
        # in v1; cast lets the test focus on factory wiring rather than a real
        # repo construction (which would require a markdown vault on disk).
        sentinel_repo = cast(ZettelRepository, object())
        pipeline = get_pipeline(doc_settings, sentinel_repo)

        assert isinstance(pipeline, Pipeline)
        services = getattr(pipeline, "_services")
        assert isinstance(services, PipelineServices)
        assert isinstance(services.state_db, StateDB)
        assert isinstance(services.ocr_runner, OCRRunner)
        assert isinstance(services.classifier, Classifier)
        assert isinstance(services.extractor, Extractor)
        assert isinstance(services.registry, IssuerRegistry)
        assert isinstance(services.zettel_writer, ZettelWriter)
