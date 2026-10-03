"""Backend registry: name -> adapter instance.

``claude`` and ``stub`` today; kiro/copilot land later without touching the
pipeline, because the pipeline depends only on the :class:`Backend` protocol.
``get_backend`` constructs the adapter lazily so importing this package does
not import the claude adapter's ``subprocess`` machinery when only the stub is
used (the whole CI path).
"""

from __future__ import annotations

from klyreon.backends.base import (
    Backend,
    BackendError,
    BackendReason,
    ConflictEntry,
    ConflictShape,
    CorroborationEntry,
    DoubtEntry,
    IngestPayload,
    LinkTarget,
    PayloadClaim,
    PayloadDoubtTarget,
    ZettelDraft,
)
from klyreon.backends.stub import StubBackend

__all__ = [
    "Backend",
    "BackendError",
    "BackendReason",
    "ConflictEntry",
    "ConflictShape",
    "CorroborationEntry",
    "DoubtEntry",
    "IngestPayload",
    "LinkTarget",
    "PayloadClaim",
    "PayloadDoubtTarget",
    "StubBackend",
    "ZettelDraft",
    "get_backend",
    "known_backends",
]

_BUILTIN_STATIC = frozenset({"stub"})


def known_backends() -> frozenset[str]:
    """Return the set of backend names ``get_backend`` can construct."""
    return _BUILTIN_STATIC


def get_backend(name: str, *, model: str | None = None, timeout_cushion: int = 30) -> Backend:
    """Construct the backend adapter registered under ``name``.

    Args:
        name: ``stub`` today; ``claude`` is wired in Phase 1 when its adapter
            lands, and kiro/copilot later.
        model: Passed to a real adapter as ``--model`` when set; ignored by the
            stub.
        timeout_cushion: Seconds added to the per-source timeout for the
            subprocess hard kill (real adapters only).

    Raises:
        BackendError: when ``name`` is not a known backend.
    """
    _ = (model, timeout_cushion)  # consumed by real adapters wired in Phase 1
    if name == "stub":
        return StubBackend()
    msg = f"unknown backend {name!r}; known backends are {sorted(known_backends())}"
    raise BackendError(BackendReason.EXIT, msg)
