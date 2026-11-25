from __future__ import annotations

import os
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from buvis.pybase.configuration.settings import GlobalSettings
from buvis.pybase.updater import check_and_update


class TestSuiteGuards:
    def test_every_test_runs_with_auto_update_disabled(self) -> None:
        assert os.environ.get("BUVIS_DEV_MODE") == "1"

    def test_cli_auto_update_check_never_reaches_the_installer(self) -> None:
        settings = cast(GlobalSettings, SimpleNamespace(auto_update=True, installer=None))
        with patch("buvis.pybase.updater.detect_installer") as detect:
            check_and_update(settings)
        detect.assert_not_called()
