from __future__ import annotations

from .exceptions import OutlookAppointmentCreationFailedError
from .outlook_local import OutlookLocalAdapter

__all__ = ["OutlookAppointmentCreationFailedError", "OutlookLocalAdapter"]
