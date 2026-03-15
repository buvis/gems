"""Services for ensuring consistency in Zettel data entities."""

from __future__ import annotations

from buvis.pybase.zettel.domain.entities.zettel.fixers.align_h1_to_title import align_h1_to_title
from buvis.pybase.zettel.domain.entities.zettel.fixers.fix_title_format import fix_title_format
from buvis.pybase.zettel.domain.entities.zettel.fixers.remove_duplicate_tags import remove_duplicate_tags
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_date import set_default_date
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_id import set_default_id
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_processed import set_default_processed
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_publish import set_default_publish
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_tags import set_default_tags
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_title import set_default_title
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_type import set_default_type
from buvis.pybase.zettel.domain.entities.zettel.fixers.sort_tags import sort_tags
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ZettelConsistencyService:
    """Ensures consistency of ZettelData entities."""

    _DEFAULTS = {
        "date": set_default_date,
        "id": set_default_id,
        "title": set_default_title,
        "type": set_default_type,
        "tags": set_default_tags,
        "publish": set_default_publish,
        "processed": set_default_processed,
    }

    _POST_FIXERS = [remove_duplicate_tags, sort_tags, fix_title_format, align_h1_to_title]

    @staticmethod
    def set_missing_defaults(zettel_data: ZettelData) -> None:
        """Set default values for missing metadata fields."""
        from buvis.pybase.zettel.domain.services.base import apply_defaults

        apply_defaults(zettel_data, ZettelConsistencyService._DEFAULTS)

    @staticmethod
    def ensure_consistency(zettel_data: ZettelData) -> None:
        """Set defaults then apply consistency fixers."""
        from buvis.pybase.zettel.domain.services.base import apply_fixers

        ZettelConsistencyService.set_missing_defaults(zettel_data)
        apply_fixers(zettel_data, ZettelConsistencyService._POST_FIXERS)
