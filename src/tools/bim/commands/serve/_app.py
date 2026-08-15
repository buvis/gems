from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from bim.commands.serve._routes import router as api_router
from bim.commands.serve._security import install_security
from bim.commands.serve._sse import router as sse_router, start_watcher, stop_watcher

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    default_directory: str,
    archive_directory: str | None = None,
    host: str = "127.0.0.1",
) -> FastAPI:
    app = FastAPI(title="bim dashboard")
    app.state.default_directory = default_directory
    app.state.archive_directory = archive_directory

    install_security(app, host)

    app.include_router(api_router, prefix="/api")
    app.include_router(sse_router, prefix="/api")

    @app.on_event("startup")
    async def _startup() -> None:
        await start_watcher(default_directory)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await stop_watcher()

    if STATIC_DIR.is_dir() and any(STATIC_DIR.iterdir()):

        @app.get("/", response_class=HTMLResponse)
        async def _index() -> HTMLResponse:
            html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
            if app.state.token_in_page:
                script = f'<script>window.__BUVIS_TOKEN__ = "{app.state.buvis_token}";</script>'
                html = html.replace("</head>", f"{script}</head>", 1)
            return HTMLResponse(html)

        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    else:
        from fastapi.responses import PlainTextResponse

        @app.get("/{path:path}")
        async def _fallback(path: str) -> PlainTextResponse:
            return PlainTextResponse(
                "Frontend not built. Run: cd src/tools/bim/commands/serve/frontend && npm ci && npm run build"
            )

    return app
