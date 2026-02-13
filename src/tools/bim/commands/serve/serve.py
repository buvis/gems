from __future__ import annotations

import webbrowser


class CommandServe:
    def __init__(
        self,
        default_directory: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        *,
        no_browser: bool = False,
    ) -> None:
        self.default_directory = default_directory
        self.host = host
        self.port = port
        self.no_browser = no_browser

    def execute(self) -> None:
        from bim.commands.serve._app import create_app

        app = create_app(self.default_directory)

        if not self.no_browser:
            webbrowser.open(f"http://{self.host}:{self.port}")

        import uvicorn

        uvicorn.run(app, host=self.host, port=self.port, log_level="info")
