"""Security primitives for the ``bim serve`` HTTP server.

Provides request-derived path confinement, a per-process auth token, and
Host validation. Remote browser access uses HTTP Basic auth through an SSH
tunnel; HTTP itself does not encrypt credentials.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.adapters import console
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

TOKEN_HEADER = "X-Buvis-Token"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass
class AppState:
    """Directories a request-derived path is allowed to resolve into."""

    default_directory: str
    archive_directory: str | None
    # The ``<business_root>/_triage/`` directory (PRD 00057). Doc triage
    # proposals live here, under business_root, which is NOT the zettel vault —
    # so it must be added to the confine_path allow-list explicitly for the
    # triage_approve action to resolve a proposal path. None when the tool has
    # no [doc] config (the doc actions are then unavailable).
    business_triage_root: str | None = None
    # Full doc settings, needed by the doc-action handlers to build command
    # services via the composition root. None when [doc] is not configured.
    doc_settings: Any = None
    # Root for project resources folders (the create_project_dir hook).
    path_projects: str | None = None
    # Daily notes folder (create logs new notes there) and the articles archive.
    path_daily: str | None = None
    path_articles: str | None = None


def confine_path(file_path: str, app_state: AppState) -> Path:
    """Resolve ``file_path`` and assert it lies under an allowed root.

    Args:
        file_path: A filesystem path derived from an incoming request.
        app_state: Holds the directories the path must resolve under.

    Returns:
        The resolved, confined path.

    Raises:
        HTTPException: With status 403 if ``file_path`` is empty, fails to
            resolve, or resolves outside every allowed root.
    """
    if not file_path:
        raise HTTPException(status_code=403, detail="path is required")

    allowed_roots = [Path(app_state.default_directory).expanduser().resolve()]
    if app_state.archive_directory:
        allowed_roots.append(Path(app_state.archive_directory).expanduser().resolve())
    if app_state.business_triage_root:
        allowed_roots.append(Path(app_state.business_triage_root).expanduser().resolve())

    try:
        resolved = Path(file_path).expanduser().resolve()
    except OSError as exc:
        raise HTTPException(status_code=403, detail="path could not be resolved") from exc

    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="path is outside the allowed directories")

    return resolved


def generate_token() -> str:
    """Mint a fresh, unpredictable auth token."""
    return secrets.token_urlsafe(32)


def require_token(request: Request) -> None:
    """FastAPI dependency enforcing the per-process auth token.

    Remote browsers may supply it as the HTTP Basic password for user ``bim``.
    A nonempty explicit token header takes precedence over browser credentials.

    Raises:
        HTTPException: With status 401 if credentials do not match the token,
            or 403 for a cross-origin mutation using browser credentials.
    """
    expected = getattr(request.app.state, "buvis_token", None)
    provided = request.headers.get(TOKEN_HEADER)
    remote = not getattr(request.app.state, "token_in_page", True)
    browser_auth = remote and not provided
    if browser_auth:
        provided = _browser_token(request)

    if provided is None or expected is None or not secrets.compare_digest(provided.encode(), expected.encode()):
        headers = {"WWW-Authenticate": 'Basic realm="bim", charset="UTF-8"'} if remote else None
        raise HTTPException(status_code=401, detail="missing or invalid token", headers=headers)
    if browser_auth and request.method not in {"GET", "HEAD", "OPTIONS"}:
        # Unlike the explicit token header, browsers attach Basic credentials
        # automatically. Reject cross-origin writes before invoking any action.
        origin = request.headers.get("origin")
        expected_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if (origin is not None and origin != expected_origin) or request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(status_code=403, detail="cross-origin request rejected")


def _browser_token(request: Request) -> str | None:
    """Read the existing token from browser HTTP Basic auth, never a URL."""
    scheme, _, encoded = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        username, separator, password = base64.b64decode(encoded, validate=True).decode("utf-8").partition(":")
    except (ValueError, binascii.Error):
        return None
    return password if username == "bim" and separator else None


class RemoteTokenMiddleware:
    """Authenticate the whole remote app, including static bootstrap and SSE.

    Pure ASGI middleware leaves streaming bodies and disconnects untouched.
    Host validation wraps this middleware and runs before the auth challenge.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            try:
                require_token(Request(scope))
            except HTTPException as exc:
                response = JSONResponse(
                    {"detail": exc.detail},
                    status_code=exc.status_code,
                    headers={"Cache-Control": "no-store", **(exc.headers or {})},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def install_security(app: FastAPI, host: str) -> None:
    """Mint the app's auth token and install ``TrustedHostMiddleware``.

    Args:
        app: The FastAPI application to secure.
        host: The bind interface. Remote clients use an SSH tunnel with a
            loopback Host, so wildcard binds never imply wildcard Host trust.
    """
    token = generate_token()
    app.state.buvis_token = token

    app.state.token_in_page = host in LOOPBACK_HOSTS
    if not app.state.token_in_page:
        app.add_middleware(RemoteTokenMiddleware)
        console.warning(
            f"bim serve is bound to non-loopback host {host!r}: all requests require authentication. "
            "Connect through an SSH tunnel using localhost; sign in as bim with the private token file's contents."
        )

    allowed_hosts = [f"[{host}]" if ":" in host else host for host in sorted(LOOPBACK_HOSTS)]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts, www_redirect=False)
