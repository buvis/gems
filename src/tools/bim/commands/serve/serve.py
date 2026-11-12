from __future__ import annotations

import signal
import webbrowser
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import FrameType

from bim.params.serve import ServeParams


def _exit_on_signal(signum: int, _frame: FrameType | None) -> None:
    raise SystemExit(128 + signum)


def _stop_like_sigterm(_signum: int, _frame: FrameType | None) -> None:
    # uvicorn shuts down gracefully on SIGTERM but ignores SIGHUP; raising
    # SystemExit here would cut the event loop short with a traceback.
    signal.raise_signal(signal.SIGTERM)


class CommandServe:
    def __init__(self, params: ServeParams) -> None:
        self.params = params

    def execute(self) -> None:
        from buvis.pybase.adapters import console
        from buvis.pybase.filesystem.atomic_write import atomic_write_text

        from bim.commands.serve._app import create_app

        app = create_app(
            self.params.default_directory,
            self.params.archive_directory,
            host=self.params.host,
            business_triage_root=self.params.business_triage_root,
            doc_settings=self.params.doc_settings,
            path_projects=self.params.path_projects,
            path_daily=self.params.path_daily,
            path_articles=self.params.path_articles,
        )

        import uvicorn

        with ExitStack() as stack:
            if not app.state.token_in_page:
                directory = stack.enter_context(TemporaryDirectory(prefix="bim-serve-"))
                token_path = Path(directory) / "token"
                atomic_write_text(token_path, app.state.buvis_token, mode=0o600)
                console.info(f"Private token file: {token_path} (removed when the server stops)")
                # uvicorn re-raises SIGTERM after shutdown; with the default handler
                # that kills the process before the token directory unwinds.
                for name, handler in (("SIGTERM", _exit_on_signal), ("SIGHUP", _stop_like_sigterm)):
                    signum = getattr(signal, name, None)
                    if signum is not None:
                        stack.callback(signal.signal, signum, signal.signal(signum, handler))

            if not self.params.no_browser and app.state.token_in_page:
                browser_host = f"[{self.params.host}]" if ":" in self.params.host else self.params.host
                webbrowser.open(f"http://{browser_host}:{self.params.port}")

            uvicorn.run(
                app,
                host=self.params.host,
                port=self.params.port,
                log_level="info",
                access_log=False,
            )
