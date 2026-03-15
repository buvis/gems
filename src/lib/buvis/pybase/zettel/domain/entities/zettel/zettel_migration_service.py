"""Services for migrating ZettelData."""

from __future__ import annotations

from buvis.pybase.zettel.domain.entities.zettel.upgrades.move_tag_to_tags import move_tag_to_tags
from buvis.pybase.zettel.domain.entities.zettel.upgrades.move_zkn_id_to_id import move_zkn_id_to_id
from buvis.pybase.zettel.domain.entities.zettel.upgrades.normalize_type import normalize_type
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ZettelMigrationService:
    """Orchestrates migration steps for Zettel data."""

    _UPGRADES = [move_zkn_id_to_id, move_tag_to_tags, normalize_type]

    @staticmethod
    def migrate(zettel_data: ZettelData) -> None:
        """Migrate zettel data through transformation steps."""
        from buvis.pybase.zettel.domain.services.base import apply_fixers

        apply_fixers(zettel_data, ZettelMigrationService._UPGRADES)
