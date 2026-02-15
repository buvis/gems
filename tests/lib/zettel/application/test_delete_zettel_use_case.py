from __future__ import annotations

from unittest.mock import MagicMock

from buvis.pybase.zettel.application.use_cases.delete_zettel_use_case import DeleteZettelUseCase
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter


class TestDeleteZettelUseCase:
    def test_calls_writer_delete(self) -> None:
        writer = MagicMock(spec=ZettelWriter)
        zettel = MagicMock(spec=Zettel)

        DeleteZettelUseCase(writer).execute(zettel)

        writer.delete.assert_called_once_with(zettel)
