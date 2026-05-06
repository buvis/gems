from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bim.commands.doc.ingest.ingest import CommandIngest
from bim.commands.doc.shared.health import MissingDependency
from bim.params.doc_ingest import IngestParams
from buvis.pybase.result import CommandResult


@pytest.fixture
def staging_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "input.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfake\n")
    return pdf


class TestCommandIngest:
    def test_delegates_to_pipeline_run(self, staging_pdf: Path) -> None:
        pipeline = MagicMock()
        expected = CommandResult(success=True, metadata={"outcome": "filed"})
        pipeline.run.return_value = expected

        params = IngestParams(source="download", staging_path=staging_pdf)
        result = CommandIngest(params=params, pipeline=pipeline).execute()

        assert result is expected
        pipeline.run.assert_called_once_with(params)

    def test_missing_dependency_returns_failure_result(self, staging_pdf: Path) -> None:
        pipeline = MagicMock()
        pipeline.run.side_effect = MissingDependency("ocrmypdf not found on PATH")

        params = IngestParams(source="scan", staging_path=staging_pdf)
        result = CommandIngest(params=params, pipeline=pipeline).execute()

        assert result.success is False
        assert "ocrmypdf" in (result.error or "")
        assert result.metadata.get("missing_dependency") is True
