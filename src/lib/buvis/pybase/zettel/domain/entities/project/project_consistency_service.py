"""Services for ensuring consistency in project zettels."""

from __future__ import annotations

from buvis.pybase.zettel.domain.entities.project.fixers.fix_lists_bullets import fix_lists_bullets
from buvis.pybase.zettel.domain.entities.project.fixers.normalize_sections_order import normalize_sections_order
from buvis.pybase.zettel.domain.entities.project.fixers.set_default_completed import set_default_completed
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ProjectZettelConsistencyService:
    """Ensures consistency in project zettels."""

    _FIXERS = [fix_lists_bullets, normalize_sections_order, set_default_completed]

    @staticmethod
    def ensure_consistency(zettel_data: ZettelData) -> None:
        """Apply consistency fixes to project zettel data."""
        from buvis.pybase.zettel.domain.services.base import apply_fixers

        apply_fixers(zettel_data, ProjectZettelConsistencyService._FIXERS)
