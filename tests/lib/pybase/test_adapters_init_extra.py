from __future__ import annotations

import os
from unittest.mock import patch


class TestAdaptersOutlookLocalLazyImport:
    def test_outlook_local_non_windows(self) -> None:
        """On non-Windows, accessing OutlookLocalAdapter raises AttributeError."""
        if os.name == "nt":
            return
        from buvis.pybase import adapters

        try:
            _ = adapters.OutlookLocalAdapter
            assert False, "Should have raised AttributeError"
        except AttributeError:
            pass

    def test_outlook_local_windows(self) -> None:
        """On Windows (mocked), OutlookLocalAdapter import is attempted."""
        from buvis.pybase import adapters

        with patch.object(os, "name", "nt"):
            try:
                _ = adapters.__getattr__("OutlookLocalAdapter")
            except (ImportError, ModuleNotFoundError, AttributeError):
                pass  # expected when module isn't installed
