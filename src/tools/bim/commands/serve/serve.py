from __future__ import annotations

import webbrowser

from bim.params.serve import ServeParams


class CommandServe:
    def __init__(self, params: ServeParams) -> None:
        self.params = params

    def execute(self) -> None:
        from bim.commands.serve._app import create_app

        app = create_app(
            self.params.default_directory,
            self.params.archive_directory,
        )

        if not self.params.no_browser:
            webbrowser.open(f"http://{self.params.host}:{self.params.port}")

        import uvicorn

        uvicorn.run(
            app,
            host=self.params.host,
            port=self.params.port,
            log_level="info",
        )
