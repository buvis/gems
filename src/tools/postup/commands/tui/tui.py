"""The ``postup tui`` command — launch the interactive Textual standup.

Loads the view-model through the pure derive layer, constructs
:class:`postup.adapters.tui.app.PostupApp`, and runs it. Returns a
:class:`CommandResult`; a missing ``data.json`` is a friendly failure ("run
postup collect first") rather than an empty screen.

Importing this module pulls in the Textual app (and thus Textual). The CLI layer
catches an ``ImportError`` from a missing ``postup`` extra and renders install
guidance via ``console.require_import`` — no traceback ever reaches the user.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from postup.adapters.tui.app import PostupApp
from postup.domain.derive import load_view_model

if TYPE_CHECKING:
    from postup.settings import PostupSettings

__all__ = ["CommandTui"]


class CommandTui:
    """Open the interactive Textual standup over the collected contracts.

    Args:
        settings: Resolved postup settings (``out_dir``).
        app_factory: Callable building the app from the view-model (injected for
            testing; defaults to :class:`PostupApp`).
    """

    def __init__(self, settings: PostupSettings, *, app_factory: type[PostupApp] = PostupApp) -> None:
        self.settings = settings
        self._app_factory = app_factory

    def execute(self) -> CommandResult:
        """Load the view-model and run the TUI.

        Returns:
            A failure result with "run postup collect first" guidance when no
            ``data.json`` exists; a success result after the app exits.
        """
        out_dir = self.settings.resolved_out_dir
        vm = load_view_model(out_dir)
        if vm.needs_collect:
            return CommandResult(
                success=False,
                error=f"no data.json in {out_dir} — run 'postup collect' first",
            )

        self._app_factory(vm).run()
        return CommandResult(success=True, output="tui closed")
