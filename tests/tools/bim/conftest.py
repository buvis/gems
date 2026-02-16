from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

MINIMAL_ZETTEL = """\
---
title: Original Title
type: note
tags:
  - alpha
  - beta
processed: false
publish: false
---

## Content

Some body text.
"""


@pytest.fixture
def minimal_zettel() -> str:
    return MINIMAL_ZETTEL


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def format_note_mocks():
    with (
        patch("bim.commands.format_note.format_note.get_repo") as mock_repo,
        patch("bim.commands.format_note.format_note.ReadZettelUseCase") as mock_reader_cls,
        patch("bim.commands.format_note.format_note.get_formatter") as mock_get_formatter,
    ):
        mock_repo.return_value = MagicMock()
        note = MagicMock()
        note.get_data.return_value = {"title": "Test Note"}
        mock_reader_cls.return_value.execute.return_value = note
        mock_get_formatter.return_value.format.return_value = "formatted content"
        yield {
            "mock_repo": mock_repo,
            "mock_reader_cls": mock_reader_cls,
            "mock_get_formatter": mock_get_formatter,
            "note": note,
        }
