"""
This module defines the ZettelFactory class which is responsible for creating instances of
:class:`zettel_entities.Zettel`.

Imports:
    - :class:`zettel.domain.entities` for accessing Zettel entities.
    - :class:`buvis.pybase.formatting.StringOperator` for string operations.
"""

from __future__ import annotations

from typing import cast

import buvis.pybase.zettel.domain.entities as zettel_entities
from buvis.pybase.formatting import StringOperator


class ZettelFactory:
    """
    A factory class for creating Zettels.

    Zettel is downcasted Zettel entity based on the zettel type.
    """

    @staticmethod
    def create(zettel: zettel_entities.Zettel) -> zettel_entities.Zettel:
        """
        Create a Zettel instance, potentially downcasting it to a more specific type based on its 'type' attribute.

        :param zettel: The original Zettel instance.
        :type zettel: :class:`zettel.domain.entities.zettel.zettel.Zettel`
        :return: A Zettel instance, either the original or a downcasted version (aka Zettel).
        :rtype: :class:`zettel.domain.entities.zettel.zettel.Zettel`
        """
        zettel_type = getattr(zettel, "type", "")

        if zettel_type in ("note", ""):  # generic Zettel
            return zettel

        # Try downcasting to more specific Zettel type
        class_name = StringOperator.camelize(zettel_type) + "Zettel"

        try:
            entity_class = cast(
                type[zettel_entities.Zettel],
                getattr(zettel_entities, class_name),
            )
        except AttributeError:
            return zettel
        else:
            if zettel.from_rust:
                downcasted_zettel = entity_class(zettel.get_data(), from_rust=True)
            else:
                downcasted_zettel = entity_class()
                downcasted_zettel.replace_data(zettel.get_data())
            return downcasted_zettel
