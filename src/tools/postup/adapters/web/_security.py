"""Security primitives for the ``postup serve`` HTTP server.

Mirrors the ``bim serve`` posture (PRD 00042): request-derived path
confinement, a per-process auth token, and ``TrustedHostMiddleware`` wiring so
the server is safe to bind on a loopback interface. The one allowed root here
is the postup ``out_dir`` — every request-derived filesystem path must
``resolve()`` under it before any read (the AGENTS.md confine-request-paths
invariant).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from buvis.pybase.adapters import console
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware

TOKEN_HEADER = "X-Buvis-Token"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass
class AppState:
    """The directory a request-derived path is allowed to resolve into."""

    out_dir: str


def confine_path(file_path: str, app_state: AppState) -> Path:
    """Resolve ``file_path`` and assert it lies under ``out_dir``.

    Args:
        file_path: A filesystem path derived from an incoming request.
        app_state: Holds the ``out_dir`` the path must resolve under.

    Returns:
        The resolved, confined path.

    Raises:
        HTTPException: With status 403 if ``file_path`` is empty, fails to
            resolve, or resolves outside ``out_dir``.
    """
    if not file_path:
        raise HTTPException(status_code=403, detail="path is required")

    allowed_root = Path(app_state.out_dir).expanduser().resolve()

    try:
        resolved = Path(file_path).expanduser().resolve()
    except OSError as exc:
        raise HTTPException(status_code=403, detail="path could not be resolved") from exc

    if not resolved.is_relative_to(allowed_root):
        raise HTTPException(status_code=403, detail="path is outside the allowed directory")

    return resolved


def generate_token() -> str:
    """Mint a fresh, unpredictable auth token."""
    return secrets.token_urlsafe(32)


def require_token(request: Request) -> None:
    """FastAPI dependency enforcing the per-process auth token.

    Raises:
        HTTPException: With status 401 if the request's token header is
            missing or does not match ``request.app.state.buvis_token``.
    """
    expected = getattr(request.app.state, "buvis_token", None)
    provided = request.headers.get(TOKEN_HEADER)

    if provided is None or expected is None or not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="missing or invalid token")


def install_security(app: FastAPI, host: str) -> None:
    """Mint the app's auth token and install ``TrustedHostMiddleware``.

    Args:
        app: The FastAPI application to secure.
        host: The interface the server is bound to; loopback hosts get a
            tight allow-list, anything else falls back to a wildcard.
    """
    token = generate_token()
    app.state.buvis_token = token

    if host in LOOPBACK_HOSTS:
        allowed_hosts = list(LOOPBACK_HOSTS)
        app.state.token_in_page = True
    else:
        allowed_hosts = ["*"]
        app.state.token_in_page = False
        console.warning(
            f"postup serve is bound to non-loopback host {host!r}: any host that can reach "
            "this port can read portfolio data without the auth token. The token is not "
            f"embedded in the page; use it for authenticated requests: {token}"
        )

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
