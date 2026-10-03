"""The offline stub backend: a real, intentional test double.

``StubBackend`` is shipped code, not a placeholder. It holds a mapping of
canned :class:`IngestPayload` objects and returns one per ``run`` call, so the
whole ingest pipeline runs in CI with no network and no operator CLI installed
(PRD "Backend contract", discovery criterion "runs offline in CI").

Two ways to drive it:

- ``StubBackend(payloads=[p1, p2, ...])`` returns them in order, one per call.
  This is the inbox-sweep shape: the pipeline calls the backend once per source.
- ``StubBackend(by_marker={...})`` returns the payload whose marker appears in
  the prompt. The fixture corpus embeds a stable marker line in each source so a
  single stub can serve a mixed sweep deterministically.

A ``run`` with no payload left (or no marker match) raises
:class:`BackendError` with ``reason="parse"`` -- a stub that was asked for more
than it was given is a test wiring bug, surfaced loudly rather than silently
returning an empty payload.
"""

from __future__ import annotations

from klyreon.backends.base import Backend, BackendError, BackendReason, IngestPayload

__all__ = ["StubBackend"]


class StubBackend(Backend):
    """Return canned payloads offline. Shipped double, not a placeholder."""

    name = "stub"

    def __init__(
        self,
        payloads: list[IngestPayload] | None = None,
        *,
        by_marker: dict[str, IngestPayload] | None = None,
    ) -> None:
        self._queue = list(payloads or [])
        self._by_marker = dict(by_marker or {})

    def run(self, prompt: str, timeout: int) -> IngestPayload:  # noqa: ARG002 - timeout unused offline
        """Return the next canned payload, or the one its marker matches."""
        if self._by_marker:
            for marker, payload in self._by_marker.items():
                if marker in prompt:
                    return payload
            markers = sorted(self._by_marker)
            msg = f"stub backend: no canned payload matches any marker in the prompt (markers: {markers})"
            raise BackendError(BackendReason.PARSE, msg)

        if not self._queue:
            msg = "stub backend: no canned payload left to return (more run() calls than payloads provided)"
            raise BackendError(BackendReason.PARSE, msg)
        return self._queue.pop(0)
