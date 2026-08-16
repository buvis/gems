"""Tests for click-related import/patch-install-timing side effects.

Split out of test_click_integration.py: these cases exercise a distinct
concern (when the parse_args monkeypatch installs, and what importing/
constructing configuration objects does or does not pull in) and each
runs in a fresh subprocess rather than in-process.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run_isolated(code: str) -> None:
    """Run *code* in a fresh interpreter and assert it exits cleanly."""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")


class TestParseArgsPatchInstallation:
    """Tests for when the parse_args monkeypatch gets installed.

    _parse_args_patch_installed is a plain module global with no test-fixture
    reset, and other tests in this file legitimately decorate commands with
    @buvis_options, which installs the patch permanently for the rest of the
    pytest process. Each case here therefore runs in a fresh subprocess so
    the assertion is not collection-order-dependent.
    """

    def test_import_alone_does_not_patch_command_parse_args(self) -> None:
        """Merely importing click_integration must not patch click.Command.parse_args."""
        code = (
            "import click\n"
            "original = click.Command.parse_args\n"
            "import buvis.pybase.configuration.click_integration\n"
            "assert click.Command.parse_args is original, 'import patched click.Command.parse_args'\n"
        )
        _run_isolated(code)

    def test_bare_decorator_patches_command_parse_args(self) -> None:
        """Bare @buvis_options still installs the click.Command.parse_args patch."""
        code = (
            "import click\n"
            "original = click.Command.parse_args\n"
            "from buvis.pybase.configuration import buvis_options\n"
            "\n"
            "@click.command()\n"
            "@buvis_options\n"
            "def cmd():\n"
            "    pass\n"
            "\n"
            "assert click.Command.parse_args is not original, "
            "'bare @buvis_options did not patch click.Command.parse_args'\n"
        )
        _run_isolated(code)

    def test_settings_class_kwarg_patches_command_parse_args(self) -> None:
        """@buvis_options(settings_class=X) (factory form) still installs the patch."""
        code = (
            "import click\n"
            "original = click.Command.parse_args\n"
            "from buvis.pybase.configuration import buvis_options\n"
            "from buvis.pybase.configuration.settings import GlobalSettings\n"
            "\n"
            "class CustomSettings(GlobalSettings):\n"
            "    custom_field: str = 'default'\n"
            "\n"
            "@click.command()\n"
            "@buvis_options(settings_class=CustomSettings)\n"
            "def cmd():\n"
            "    pass\n"
            "\n"
            "assert click.Command.parse_args is not original, "
            "'@buvis_options(settings_class=...) did not patch click.Command.parse_args'\n"
        )
        _run_isolated(code)

    def test_bare_decorator_on_group_patches_group_parse_args(self) -> None:
        """Bare @buvis_options on a click.Group still installs the click.Group.parse_args patch."""
        code = (
            "import click\n"
            "original = click.Group.parse_args\n"
            "from buvis.pybase.configuration import buvis_options\n"
            "\n"
            "@click.group()\n"
            "@buvis_options\n"
            "def cli():\n"
            "    pass\n"
            "\n"
            "assert click.Group.parse_args is not original, "
            "'bare @buvis_options did not patch click.Group.parse_args'\n"
        )
        _run_isolated(code)

    def test_second_application_does_not_repatch(self) -> None:
        """A second @buvis_options application does not stack another patch layer."""
        code = (
            "import click\n"
            "from buvis.pybase.configuration import buvis_options\n"
            "\n"
            "@click.command()\n"
            "@buvis_options\n"
            "def cmd1():\n"
            "    pass\n"
            "\n"
            "after_first = click.Command.parse_args\n"
            "\n"
            "@click.command()\n"
            "@buvis_options\n"
            "def cmd2():\n"
            "    pass\n"
            "\n"
            "assert click.Command.parse_args is after_first, "
            "'second buvis_options application re-patched click.Command.parse_args'\n"
        )
        _run_isolated(code)


class TestConfigurationImportSideEffects:
    """Tests for import-time side effects of buvis.pybase.configuration.

    Other tests in this file permanently patch Click via @buvis_options, which
    would make an in-process assertion collection-order-dependent. This case
    therefore runs in a fresh subprocess, matching TestParseArgsPatchInstallation.
    """

    def test_constructing_global_settings_does_not_patch_click_or_import_updater(self) -> None:
        """Importing GlobalSettings from the top-level configuration package and
        constructing it must not patch click.Command.parse_args, must not
        import buvis.pybase.updater, and must not import the click_integration
        submodule (the eager re-export in configuration/__init__.py must be lazy)."""
        code = (
            "import sys\n"
            "import click\n"
            "original = click.Command.parse_args\n"
            "from buvis.pybase.configuration import GlobalSettings\n"
            "GlobalSettings()\n"
            "assert click.Command.parse_args is original, "
            "'constructing GlobalSettings patched click.Command.parse_args'\n"
            "assert 'buvis.pybase.updater' not in sys.modules, "
            "'constructing GlobalSettings imported buvis.pybase.updater'\n"
            "assert 'buvis.pybase.configuration.click_integration' not in sys.modules, "
            "'constructing GlobalSettings imported buvis.pybase.configuration.click_integration'\n"
        )
        _run_isolated(code)

    def test_loading_global_settings_does_not_import_click_at_all(self) -> None:
        """Importing and constructing GlobalSettings must not import click at all.

        The case above imports click itself before importing configuration, so it
        can only prove the parse_args patch was not applied — it cannot prove click
        stays unloaded, because it loaded click first. This case never imports click,
        so it actually proves the lazy-import claim.
        """
        code = (
            "import sys\n"
            "from buvis.pybase.configuration import GlobalSettings\n"
            "GlobalSettings()\n"
            "assert 'click' not in sys.modules, 'click was imported'\n"
            "assert 'buvis.pybase.updater' not in sys.modules, 'updater was imported'\n"
        )
        _run_isolated(code)

    def test_unknown_attribute_raises(self) -> None:
        """Mirrors the adapters/__init__.py precedent (test_import_unknown_raises in
        tests/lib/pybase/test_adapters_init.py): accessing an unrecognized name on
        buvis.pybase.configuration must raise AttributeError via the lazy __getattr__
        fallback, not silently return None or import something unintended. No global
        state is touched, so this runs in-process rather than via subprocess."""
        with pytest.raises(AttributeError, match="has no attribute"):
            from buvis.pybase import configuration

            configuration.__getattr__("NonExistentSetting")
