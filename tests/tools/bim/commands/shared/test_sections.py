from __future__ import annotations

from bim.commands.shared.sections import replace_section
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestReplaceSection:
    def test_replaces_existing_section(self) -> None:
        data = ZettelData()
        data.sections = [("# Title", ""), ("## Notes", "old content")]

        replace_section(data, "## Notes", "new content")

        assert data.sections == [("# Title", ""), ("## Notes", "new content")]

    def test_appends_when_heading_not_found(self) -> None:
        data = ZettelData()
        data.sections = [("# Title", "")]

        replace_section(data, "## New", "some content")

        assert data.sections == [("# Title", ""), ("## New", "some content")]

    def test_preserves_other_sections(self) -> None:
        data = ZettelData()
        data.sections = [("# A", "a"), ("# B", "b"), ("# C", "c")]

        replace_section(data, "# B", "updated")

        assert data.sections == [("# A", "a"), ("# B", "updated"), ("# C", "c")]
