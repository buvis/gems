from buvis.pybase.zettel.domain.entities.project.services.consistency.fixers.fix_lists_bullets import (
    fix_lists_bullets,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_fix_lists_bullets():
    # Create a sample ZettelData object
    zettel_data = ZettelData()
    zettel_data.sections = [
        ("Section 1", "Content with * bullet\n* Another bullet"),
        ("Section 2", "Normal content\nNo bullets here"),
        ("Section 3", "* First item\n* Second item\nThird item"),
        ("Section 4", "- Fourth item\n* Fifth item"),
    ]

    # Call the function
    fix_lists_bullets(zettel_data)

    # Assert the changes
    assert zettel_data.sections == [
        ("Section 1", "Content with * bullet\n- Another bullet"),
        ("Section 2", "Normal content\nNo bullets here"),
        ("Section 3", "- First item\n- Second item\nThird item"),
        ("Section 4", "- Fourth item\n- Fifth item"),
    ]
