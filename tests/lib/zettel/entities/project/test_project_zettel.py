from unittest.mock import MagicMock, patch

from buvis.pybase.zettel.domain.entities.project.project import ProjectZettel
from buvis.pybase.zettel.domain.entities.project.services.consistency.project_zettel_consistency_service import (
    ProjectZettelConsistencyService,
)
from buvis.pybase.zettel.domain.entities.project.services.migration.project_zettel_migration_service import (
    ProjectZettelMigrationService,
)
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel


class TestProjectZettel:
    def test_init_calls_super_init(self):
        with patch.object(Zettel, "__init__") as mock_super_init:
            _ = ProjectZettel()
            mock_super_init.assert_called_once()

    def test_migrate_calls_super_and_service(self):
        with (
            patch.object(Zettel, "_migrate") as mock_super_migrate,
            patch.object(ProjectZettelMigrationService, "migrate") as mock_migrate_service,
        ):
            zettel = ProjectZettel()
            zettel._data = MagicMock()
            zettel._migrate()
            mock_super_migrate.assert_called_once()
            mock_migrate_service.assert_called_once_with(zettel._data)

    def test_ensure_consistency_calls_super_and_service(self):
        with (
            patch.object(Zettel, "_ensure_consistency") as mock_super_consistency,
            patch.object(ProjectZettelConsistencyService, "ensure_consistency") as mock_consistency_service,
        ):
            zettel = ProjectZettel()
            zettel._data = MagicMock()
            zettel._ensure_consistency()
            mock_super_consistency.assert_called_once()
            mock_consistency_service.assert_called_once_with(zettel._data)

    def test_log_returns_correct_section(self):
        zettel = ProjectZettel()
        zettel._data = MagicMock()
        zettel._data.sections = [
            ("## Log", "Log content"),
            ("## Other", "Other content"),
        ]
        assert zettel.log == "Log content"

    def test_log_returns_empty_if_no_log_section(self):
        zettel = ProjectZettel()
        zettel._data = MagicMock()
        zettel._data.sections = [("## Other", "Other content")]
        assert zettel.log == ""
