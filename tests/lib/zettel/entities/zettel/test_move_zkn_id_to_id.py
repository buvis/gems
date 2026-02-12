from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.services.migration.upgrades.move_zkn_id_to_id import (
    move_zkn_id_to_id,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_move_zkn_id_to_id():
    # Setup
    metadata = {"zkn-id": "12345"}
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = metadata

    # Exercise
    move_zkn_id_to_id(zettel_data)

    # Verify
    assert "id" in zettel_data.metadata
    assert zettel_data.metadata["id"] == "12345"
    assert "zkn-id" not in zettel_data.metadata


def test_no_zkn_id_present():
    # Setup
    metadata = {"id": "existing"}
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = metadata

    # Exercise
    move_zkn_id_to_id(zettel_data)

    # Verify
    assert zettel_data.metadata["id"] == "existing"
    assert "zkn-id" not in zettel_data.metadata


def test_both_id_and_zkn_id_present():
    # Setup
    metadata = {"id": "existing", "zkn-id": "new"}
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = metadata

    # Exercise
    move_zkn_id_to_id(zettel_data)

    # Verify
    assert zettel_data.metadata["id"] == "existing"
    assert "zkn-id" not in zettel_data.metadata
