from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def replace_section(data: ZettelData, heading: str, value: str) -> None:
    """Replace section body by heading, or append if not found."""
    replaced = False
    new_sections: list[tuple[str, str]] = []
    for h, old_body in data.sections:
        if h == heading:
            new_sections.append((h, value))
            replaced = True
        else:
            new_sections.append((h, old_body))
    if not replaced:
        new_sections.append((heading, value))
    data.sections = new_sections
