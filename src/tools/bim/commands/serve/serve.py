from __future__ import annotations

import webbrowser
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

from bim.params.serve import ServeParams


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
