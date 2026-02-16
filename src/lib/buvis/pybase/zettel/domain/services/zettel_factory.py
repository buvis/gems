from __future__ import annotations

from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel.domain.entities import ProjectZettel, Zettel

# Add new Zettel subtypes here (key = class name, value = class)
_ENTITY_CLASSES: dict[str, type[Zettel]] = {"ProjectZettel": ProjectZettel}


class ZettelFactory:
    """
    A factory class for creating Zettels.

    Zettel is downcasted Zettel entity based on the zettel type.
    """

    @staticmethod
    def create(zettel: Zettel) -> Zettel:
        """Create a Zettel instance, potentially downcasting it based on its type attribute.

        Args:
            zettel: The original Zettel instance.

        Returns:
            A Zettel instance, either the original or a downcasted version (aka Zettel).
        """
        zettel_type = getattr(zettel, "type", "") or ""

        if zettel_type in ("note", ""):  # generic Zettel
            if not zettel.from_rust:
                zettel.ensure_consistency()
                zettel.migrate()
                zettel.ensure_consistency()
            return zettel

        # Try downcasting to more specific Zettel type
        class_name = StringOperator.camelize(zettel_type) + "Zettel"

        entity_class = _ENTITY_CLASSES.get(class_name)
        if entity_class is None:
            if not zettel.from_rust:
                zettel.ensure_consistency()
                zettel.migrate()
                zettel.ensure_consistency()
            return zettel

        if zettel.from_rust:
            downcasted_zettel = entity_class(zettel.get_data(), from_rust=True)
        else:
            downcasted_zettel = entity_class()
            downcasted_zettel.replace_data(zettel.get_data())
            downcasted_zettel.ensure_consistency()
            downcasted_zettel.migrate()
            downcasted_zettel.ensure_consistency()
        return downcasted_zettel
