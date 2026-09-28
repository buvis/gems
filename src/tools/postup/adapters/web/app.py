"""FastAPI application factory for ``postup serve``.

Builds the app that serves the committed SvelteKit build
(``adapters/web/frontend/build/``, shipped from PRD 00065/00066) and the live
payload plane. Mirrors the ``bim serve`` app-factory pattern: security wired
first (``TrustedHostMiddleware`` + per-process token via
:func:`install_security`), the API + SSE routers mounted under ``/api``, the
``out_dir`` watcher started/stopped on the app lifespan, and the static UI
mounted last with a token injected into ``index.html`` on loopback.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.adapters import console
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from postup.adapters.web._routes import router as api_router
from postup.adapters.web._security import install_security
from postup.adapters.web._sse import router as sse_router, start_watcher, stop_watcher

if TYPE_CHECKING:
    from postup.settings import PostupSettings

BUILD_DIR = Path(__file__).parent / "frontend" / "build"


def create_app(settings: PostupSettings, *, host: str = "127.0.0.1") -> FastAPI:
    """Build the configured ``postup serve`` FastAPI app.

    Args:
        settings: Resolved postup settings (``out_dir`` is the sole confinement
            root and the directory watched for SSE refreshes).
        host: Interface the server will bind to; drives the loopback vs
            wildcard ``TrustedHostMiddleware`` posture and token-in-page.

    Returns:
        The configured application.
    """
    out_dir = str(settings.resolved_out_dir)

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await start_watcher(out_dir)
        try:
            yield
        finally:
            await stop_watcher()

    app = FastAPI(title="postup dashboard", lifespan=_lifespan)
    app.state.settings = settings
    # ``out_dir`` on app.state is the single confinement root the routes resolve
    # request-derived paths against (duck-typed by confine_path's AppState).
    app.state.out_dir = out_dir

    install_security(app, host)

    app.include_router(api_router, prefix="/api")
    app.include_router(sse_router, prefix="/api")

    if BUILD_DIR.is_dir() and any(BUILD_DIR.iterdir()):

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def _index() -> HTMLResponse:
            index_path = BUILD_DIR / "index.html"
            if not index_path.is_file():
                raise HTTPException(status_code=404, detail="index.html not found")
            html = index_path.read_text(encoding="utf-8")
            if app.state.token_in_page:
                script = f'<script>window.__BUVIS_TOKEN__ = "{app.state.buvis_token}";</script>'
                if "</head>" in html:
                    html = html.replace("</head>", f"{script}</head>", 1)
                else:
                    console.warning("postup serve: index.html has no </head>; auth token was not injected")
            return HTMLResponse(html)

        app.mount("/", StaticFiles(directory=str(BUILD_DIR), html=True), name="static")
    else:
        from fastapi.responses import PlainTextResponse

        @app.get("/{path:path}", include_in_schema=False)
        async def _fallback(path: str) -> PlainTextResponse:  # noqa: ARG001  # path bound by the route
            return PlainTextResponse(
                "Frontend not built. Run: cd src/tools/postup/adapters/web/frontend && npm ci && npm run build"
            )

    return app
