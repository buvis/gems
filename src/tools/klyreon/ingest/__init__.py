"""Turn a backend payload into correct files, one source end to end.

No console, no Click. The orchestration (``ingest_source``), the pipeline and
the CLI wiring arrive in Phase 2; Phase 1 ships the pure transforms:

- :mod:`klyreon.ingest.render` -- payload drafts to validated documents.
- :mod:`klyreon.ingest.conflicts` -- the three conflict shapes + corroboration.
- :mod:`klyreon.ingest.moc` -- create/append inside the MOC marker block.
"""

from __future__ import annotations
