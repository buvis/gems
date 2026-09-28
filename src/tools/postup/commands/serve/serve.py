"""The ``postup serve`` command.

Starts the FastAPI web UI (the bim-serve app-factory pattern) on uvicorn.
fastapi/uvicorn are optional dependencies behind the ``postup-web`` extra; a
missing extra yields a :class:`CommandResult` failure carrying install guidance
rather than a traceback. Per the CommandResult discipline this class never
calls ``sys.exit`` / ``console.panic`` and never lets an exception escape — the
CLI adapter renders the returned result (and maps a missing-import result to
``console.require_import``).
"""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from postup.params.serve import ServeParams
    from postup.settings import PostupSettings

__all__ = ["MISSING_EXTRA_ERROR", "CommandServe"]

# Sentinel the CLI matches on to route a missing web extra to
# ``console.require_import`` instead of a plain failure line.
MISSING_EXTRA_ERROR = "postup-web extra is not installed"


class CommandServe:
    """Build the ``postup serve`` app and run it on uvicorn.

    Args:
        settings: Resolved postup settings (``out_dir``, host/port context).
        params: Serve parameters (host, port, no-browser).
    """

    def __init__(self, settings: PostupSettings, params: ServeParams) -> None:
        self.settings = settings
        self.params = params

    def execute(self) -> CommandResult:
        """Start the server, or return a failure result.

        Returns:
            A failure :class:`CommandResult` when the ``postup-web`` extra is
            absent or uvicorn stops with an error. On a clean shutdown (Ctrl-C)
            a success result is returned. ``uvicorn.run`` blocks until the
            server stops, so this only returns once the server is done.
        """
        try:
            import uvicorn

            from postup.adapters.web import create_app
        except ImportError:
            return CommandResult(
                success=False,
                error=MISSING_EXTRA_ERROR,
                metadata={"missing_extra": "postup-web"},
            )

        app = create_app(self.settings, host=self.params.host)

        if not self.params.no_browser:
            webbrowser.open(f"http://{self.params.host}:{self.params.port}")

        try:
            uvicorn.run(
                app,
                host=self.params.host,
                port=self.params.port,
                log_level="info",
            )
        except OSError as exc:
            return CommandResult(
                success=False,
                error=f"failed to start server on {self.params.host}:{self.params.port}: {exc}",
            )

        return CommandResult(success=True, output="postup serve stopped")
