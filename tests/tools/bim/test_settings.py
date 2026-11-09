from __future__ import annotations

from pathlib import Path

import bim
import yaml
from bim.settings import BimSettings


class TestBimDefaultVaultFolder:
    def test_default_note_directory_is_notes_folder(self) -> None:
        assert BimSettings.model_fields["path_zettelkasten"].default == "~/bim/notes/"

    def test_default_archive_directory_is_local_reference_archive(self) -> None:
        assert BimSettings.model_fields["path_archive"].default == "~/Documents/reference/40-archives/"

    def test_settings_path_projects_default(self) -> None:
        assert BimSettings.model_fields["path_projects"].default == "~/Documents/reference/10-projects/"

    def test_settings_path_daily_and_articles_defaults(self) -> None:
        assert BimSettings.model_fields["path_daily"].default == "~/bim/notes/calendar/daily/"
        assert BimSettings.model_fields["path_articles"].default == "~/Documents/reference/40-archives/articles/"

    def test_contacts_query_reads_notes_folder(self) -> None:
        contacts = Path(bim.__file__).parent / "commands" / "query" / "contacts.yaml"
        source = yaml.safe_load(contacts.read_text(encoding="utf-8"))["source"]
        assert source["directory"] == "~/bim/notes/contact"
