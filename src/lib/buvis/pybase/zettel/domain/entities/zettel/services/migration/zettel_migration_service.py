"""
This module provides services for migrating ZettelData.

Imports:
    - Various upgrade functions from buvis.pybase.zettel.domain.entities.zettel.services.migration.upgrades
    - :class:`ZettelData` from buvis.pybase.zettel.domain.value_objects.zettel_data
"""

from buvis.pybase.zettel.domain.entities.zettel.services.migration.upgrades.move_tag_to_tags import (
    move_tag_to_tags,
)
from buvis.pybase.zettel.domain.entities.zettel.services.migration.upgrades.move_zkn_id_to_id import (
    move_zkn_id_to_id,
)
from buvis.pybase.zettel.domain.entities.zettel.services.migration.upgrades.normalize_type import (
    normalize_type,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ZettelMigrationService:
    """
    Provides services for migrating Zettel data to new formats or structures.

    This class is responsible for orchestrating various migration steps to update Zettel data.
    """

    @staticmethod
    def migrate(zettel_data: ZettelData) -> None:
        """
        Migrate the given Zettel data through several transformation steps.

        :param zettel_data: The Zettel data to be migrated
        :type zettel_data: :class:`ZettelData`
        :return: None. The function modifies the `zettel_data` in place.
        """
        move_zkn_id_to_id(zettel_data)
        move_tag_to_tags(zettel_data)
        normalize_type(zettel_data)
