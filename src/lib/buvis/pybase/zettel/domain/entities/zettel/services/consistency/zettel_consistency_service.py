"""
This module provides services for ensuring consistency in Zettel data entities.
"""

from __future__ import annotations

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.align_h1_to_title import (
    align_h1_to_title,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.fix_title_format import (
    fix_title_format,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.remove_duplicate_tags import (
    remove_duplicate_tags,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_date import (
    set_default_date,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_id import (
    set_default_id,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_processed import (
    set_default_processed,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_publish import (
    set_default_publish,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_tags import (
    set_default_tags,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_title import (
    set_default_title,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_type import (
    set_default_type,
)
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.sort_tags import (
    sort_tags,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ZettelConsistencyService:
    """
    Provides services to ensure the consistency of :class:`ZettelData` entities.

    This class includes methods to set missing default values and ensure overall data consistency.
    """

    @staticmethod
    def set_missing_defaults(zettel_data: ZettelData) -> None:
        """
        Set default values for missing metadata fields in :class:`ZettelData`.

        :param zettel_data: The Zettel data to modify
        :type zettel_data: :class:`ZettelData`
        :return: None. The function modifies the `zettel_data` in place.
        """
        defaults = {
            "date": set_default_date,
            "id": set_default_id,
            "title": set_default_title,
            "type": set_default_type,
            "tags": set_default_tags,
            "publish": set_default_publish,
            "processed": set_default_processed,
        }
        for key, func in defaults.items():
            if zettel_data.metadata.get(key, None) is None:
                func(zettel_data)

    @staticmethod
    def ensure_consistency(zettel_data: ZettelData) -> None:
        """
        Ensure the consistency of :class:`ZettelData`.

        :param zettel_data: The Zettel data to check and modify
        :type zettel_data: :class:`ZettelData`
        :return: None. The function modifies the `zettel_data` in place.
        """
        ZettelConsistencyService.set_missing_defaults(zettel_data)
        remove_duplicate_tags(zettel_data)
        sort_tags(zettel_data)
        fix_title_format(zettel_data)
        align_h1_to_title(zettel_data)
