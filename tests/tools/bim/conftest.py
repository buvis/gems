from __future__ import annotations

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

