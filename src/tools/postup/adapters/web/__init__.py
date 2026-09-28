"""The ``postup`` web adapter — HTTP delivery of the portfolio UI.

Exposes :func:`create_app`, the FastAPI application factory that serves the
committed SvelteKit build and the live payload/trigger/SSE plane. All actions
delegate to the same command classes as the CLI through the composition root.
"""

from __future__ import annotations

from postup.adapters.web.app import create_app

__all__ = ["create_app"]
