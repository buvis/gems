"""
This module provides the ProjectZettelMigrationService class which handles the migration of project
zettel data using specific migration services.

Imports:
    - migrate_loop_log: A function from the migration services to handle loop log migrations.
    - ZettelData: A class representing the data structure for zettel information.
"""

from __future__ import annotations

from buvis.pybase.zettel.domain.entities.project.services.migration.upgrades.migrate_loop_log import (
    migrate_loop_log,
)
from buvis.pybase.zettel.domain.entities.project.services.migration.upgrades.migrate_parent_reference import (
    migrate_parent_reference,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ProjectZettelMigrationService:
    """
    Provides a service for migrating project zettel data.

    This class is designed to encapsulate the migration logic for project zettels,
    utilizing specific migration functions provided by the domain's migration services.
    """

    @staticmethod
    def migrate(zettel_data: ZettelData) -> None:
        """
        Migrate the specified zettel data using the loop log migration service.

        :param zettel_data: The zettel data to be migrated.
        :type zettel_data: :class:`ZettelData`
        :return: None. The function modifies the `zettel_data` in place.
        :rtype: None
        """
        migrate_loop_log(zettel_data)
        migrate_parent_reference(zettel_data)
