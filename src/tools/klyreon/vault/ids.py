"""14-digit zettel ID allocation with the collision-bump rule (spec 3.1).

The ID is the local-time creation timestamp rendered as ``YYYYMMDDHHmmSS``.
If ``wiki/notes/<id>.md`` already exists, the timestamp is bumped by one
second and retried until free. Both the filename and the ``created`` field
reflect the bumped value, so they always agree -- this module returns both.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

__all__ = ["AllocatedId", "allocate_id", "format_id"]


def format_id(moment: dt.datetime) -> str:
    """Render ``moment`` as a 14-digit ``YYYYMMDDHHmmSS`` id."""
    return moment.strftime("%Y%m%d%H%M%S")


@dataclass(frozen=True, slots=True)
class AllocatedId:
    """A free zettel id and the ``created`` datetime it was derived from.

    ``created`` is bumped in lockstep with ``id`` so the two always agree
    (spec 3.1 / 5.1).
    """

    id: str
    created: dt.datetime

    @property
    def filename(self) -> str:
        """The zettel filename ``<id>.md``."""
        return f"{self.id}.md"


def allocate_id(notes_dir: Path, now: dt.datetime) -> AllocatedId:
    """Return a unique id for a new zettel in ``notes_dir``.

    Starts at ``now`` and bumps by one second until ``<id>.md`` is free.

    Args:
        notes_dir: The ``wiki/notes/`` directory to check for collisions.
        now: The creation timestamp (local time, timezone-aware).

    Returns:
        An :class:`AllocatedId` whose ``id`` and ``created`` agree.
    """
    moment = now
    while True:
        candidate = format_id(moment)
        if not (notes_dir / f"{candidate}.md").exists():
            return AllocatedId(id=candidate, created=moment)
        moment = moment + dt.timedelta(seconds=1)
