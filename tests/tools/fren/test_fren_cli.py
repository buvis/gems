from __future__ import annotations

import sys
from unittest.mock import patch

from click.testing import CliRunner
from fren.cli import cli


class TestFrenSlugImportError:
    def test_slug_import_error(self, tmp_path) -> None:
        target = tmp_path / "a.txt"
        target.write_text("x")
        mod_key = "fren.commands.slug.slug"
        saved = sys.modules.pop(mod_key, None)
        try:
            with patch.dict(sys.modules, {mod_key: None}):
                runner = CliRunner()
                result = runner.invoke(cli, ["slug", str(target)])
                assert "requires the 'fren' extra" in result.output
        finally:
            if saved is not None:
                sys.modules[mod_key] = saved
