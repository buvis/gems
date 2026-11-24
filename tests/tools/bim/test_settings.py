from __future__ import annotations

import os
from pathlib import Path

import bim
import pytest
import yaml
from bim.settings import BimSettings
from buvis.pybase.configuration.resolver import ConfigResolver


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

    def test_ignores_a_config_file_in_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cloned repository must not point bim at another host (agoge 2026-11-23, finding 3)."""
        home = tmp_path / "home"
        work = tmp_path / "work"
        home.mkdir()
        work.mkdir()
        for name in [name for name in os.environ if name.upper().startswith("BUVIS_")]:
            monkeypatch.delenv(name)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.chdir(work)
        (work / "buvis-bim.yaml").write_text("ollama_url: http://127.0.0.1:9/${HOME}\ndebug: true\n", encoding="utf-8")

        settings = ConfigResolver().resolve(BimSettings)

        assert settings.ollama_url == "http://localhost:11434"
        assert settings.debug is False

    def test_contacts_query_reads_notes_folder(self) -> None:
        contacts = Path(bim.__file__).parent / "commands" / "query" / "contacts.yaml"
        source = yaml.safe_load(contacts.read_text(encoding="utf-8"))["source"]
        assert source["directory"] == "~/bim/notes/contact"
