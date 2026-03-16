"""Services for migrating project zettel data."""

from __future__ import annotations

from buvis.pybase.zettel.domain.entities.project.upgrades.migrate_loop_log import migrate_loop_log
from buvis.pybase.zettel.domain.entities.project.upgrades.migrate_parent_reference import migrate_parent_reference
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ProjectZettelMigrationService:
    """Orchestrates migration steps for project zettel data."""

    _UPGRADES = [migrate_loop_log, migrate_parent_reference]

    @staticmethod
    def migrate(zettel_data: ZettelData) -> None:
        """Migrate project zettel data through transformation steps."""
        from buvis.pybase.zettel.domain.services.base import apply_fixers

        apply_fixers(zettel_data, ProjectZettelMigrationService._UPGRADES)
