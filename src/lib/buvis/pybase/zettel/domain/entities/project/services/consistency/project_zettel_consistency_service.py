"""
This module provides services for ensuring consistency in project zettels.

It includes functions to fix list bullet formatting and normalize the order of sections
within a zettel. These functionalities are encapsulated in the ProjectZettelConsistencyService
class, which operates on instances of :class:`ZettelData`.
"""

from buvis.pybase.zettel.domain.entities.project.services.consistency.fixers.fix_lists_bullets import (
    fix_lists_bullets,
)
from buvis.pybase.zettel.domain.entities.project.services.consistency.fixers.normalize_sections_order import (
    normalize_sections_order,
)
from buvis.pybase.zettel.domain.entities.project.services.consistency.fixers.set_default_completed import (
    set_default_completed,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ProjectZettelConsistencyService:
    """
    Provides services to ensure consistency in project zettels.

    This class offers a static method to apply necessary consistency fixes to zettels,
    specifically targeting list bullet formatting and section order normalization.
    """

    @staticmethod
    def ensure_consistency(zettel_data: ZettelData) -> None:
        """
        Ensure the consistency of the given zettel data by applying various fixes.

        This method modifies the provided :class:`ZettelData` instance in place by
        fixing the list bullets and normalizing the order of sections within the zettel.

        :param zettel_data: The zettel data to be made consistent.
        :type zettel_data: :class:`ZettelData`
        :return: None. The function modifies the `zettel_data` in place.
        """
        fix_lists_bullets(zettel_data)
        normalize_sections_order(zettel_data)
        set_default_completed(zettel_data)
