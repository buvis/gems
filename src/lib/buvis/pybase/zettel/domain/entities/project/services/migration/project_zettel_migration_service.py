"""
This module provides the ProjectZettelMigrationService class which handles the migration of project
zettel data using specific migration services.
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
        """Migrate the specified zettel data using the loop log migration service.

        Args:
            zettel_data: The zettel data to be migrated.

        Returns:
            None. The function modifies the `zettel_data` in place.
        """
        migrate_loop_log(zettel_data)
        migrate_parent_reference(zettel_data)
