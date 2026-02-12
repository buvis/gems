from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelReader
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime


@pytest.fixture
def zettel_data() -> ZettelData:
    return ZettelData()


@pytest.fixture
def mock_zettel_repository() -> MagicMock:
    return MagicMock(spec=ZettelReader)


@pytest.fixture
def make_zettel() -> Callable[..., Zettel]:
    def _make_zettel(
        *,
        id: int | None = None,
        title: str | None = None,
        date: datetime | None = None,
        type: str | None = None,
        tags: list[str] | None = None,
        processed: bool = False,
        extra_meta: dict[str, Any] | None = None,
        file_path: str | None = None,
    ) -> Zettel:
        data = ZettelData()
        if id is not None:
            data.metadata["id"] = id
        if title is not None:
            data.metadata["title"] = title
        if date is not None:
            data.metadata["date"] = date
        if type is not None:
            data.metadata["type"] = type
        if tags is not None:
            data.metadata["tags"] = tags
        data.metadata["processed"] = processed
        if extra_meta:
            data.metadata.update(extra_meta)
        data.file_path = file_path
        return Zettel(data, from_rust=True)

    return _make_zettel
