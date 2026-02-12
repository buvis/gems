from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, cast

import tzlocal
from buvis.pybase.adapters.outlook_local.exceptions import (
    OutlookAppointmentCreationFailedError,
)

try:
    import win32com.client

    _win32com_available = True
except ImportError:  # pragma: no cover - not importable on CI when not on Windows
    win32com = None
    _win32com_available = False

from buvis.pybase.adapters.console.console import console


class OutlookLocalAdapter:
    """Local Outlook COM automation for calendar operations.

    .. warning:: Windows-only. Instantiating on non-Windows raises OSError.

    Requires Microsoft Outlook installed with a default calendar.

    Example:
        >>> from buvis.pybase.adapters.outlook_local.outlook_local import OutlookLocalAdapter
        >>> adapter = OutlookLocalAdapter()
        >>> adapter.create_timeblock({"subject": "Check-in",
        ...     "body": "Daily sync", "duration": 30, "categories": "Work"})
    """

    def __init__(self: OutlookLocalAdapter) -> None:
        """Connect to local Outlook application via COM.

        Initializes the MAPI namespace and default calendar (folder 9).

        Raises:
            SystemExit: Outlook connection failed (console.panic).
        """
        if os.name != "nt":
            msg = f"OS {os.name} not supported by OutlookLocalAdapter"
            raise OSError(msg)
        if not _win32com_available:
            raise OSError("win32com.client is not available on this platform")

        try:
            self.app: Any = win32com.client.Dispatch("Outlook.Application")
            self.api: Any = self.app.GetNamespace("MAPI")
            self.calendar: Any = self.api.GetDefaultFolder(9)
        except Exception as e:
            console.panic(f"Outook connection failed:\n{e}")

    def create_timeblock(
        self: OutlookLocalAdapter,
        appointment_input: dict[str, Any],
    ) -> None:
        """Create a calendar appointment.

        Args:
            appointment_input (dict): Dict with keys:
                subject (str): Appointment title
                body (str): Description text
                duration (int): Length in minutes
                location (str): Location field
                categories (str): Outlook category
                start (datetime, optional): Start time. Defaults to current hour when omitted.

        Raises:
            OutlookAppointmentCreationFailedError: If creation fails.
        """
        try:
            appointment = self.app.CreateItem(1)  # 1 represents AppointmentItem
            if appointment_input.get("start") and isinstance(
                appointment_input["start"],
                datetime,
            ):
                start = appointment_input["start"]
            else:
                start = datetime.now(tzlocal.get_localzone()).replace(
                    minute=0,
                    second=0,
                )
            appointment.Start = start
            appointment.Subject = appointment_input["subject"]
            appointment.Body = appointment_input["body"]
            appointment.Duration = appointment_input["duration"]
            appointment.Location = appointment_input["location"]
            appointment.Categories = appointment_input["categories"]
            appointment.Save()
        except Exception as e:
            msg = f"Appointment creation failed:\n{e}"
            raise OutlookAppointmentCreationFailedError(msg) from e

    def get_all_appointments(self: OutlookLocalAdapter) -> list[Any]:
        """Retrieve all calendar appointments sorted by start time.

        Returns:
            list: AppointmentItem COM objects with recurrences included.
        """
        appointments: Any = self.calendar.Items
        appointments.IncludeRecurrences = True
        appointments.Sort("[Start]")
        return cast(list[Any], appointments)

    def get_day_appointments(
        self: OutlookLocalAdapter,
        appointments: Any,
        date: datetime,
    ) -> list[Any]:
        """Filter appointments to a single day.

        Args:
            appointments (Any): Collection from get_all_appointments.
            date (datetime): datetime for the target day.

        Returns:
            list: AppointmentItems for that day.
        """
        restrict_from = date.strftime("%Y-%m-%d")
        restrict_to_str = (date + timedelta(days=1)).strftime("%Y-%m-%d")
        restrict_query = f"[Start] >= '{restrict_from}' AND [End] <= '{restrict_to_str}'"
        appointments = appointments.Restrict(restrict_query)
        return [
            appointment
            for appointment in appointments
            if (
                appointment.Start.year == date.year
                and appointment.Start.month == date.month
                and appointment.Start.day == date.day
            )
        ]

    def get_conflicting_appointment(
        self: OutlookLocalAdapter,
        desired_start: datetime,
        desired_duration: int,
        debug_level: int = 0,
    ) -> Any | None:
        """Find appointment conflicting with proposed time slot.

        Appointments are sorted by `Start`, so the method terminates early when possible.

        Args:
            desired_start (datetime): Proposed start datetime
            desired_duration (int): Proposed duration in minutes
            debug_level (int): If >0, prints collision check details

        Returns:
            Any | None: Conflicting Outlook AppointmentItem COM object, or None if slot is free.
        """
        appointments = self.get_day_appointments(
            self.get_all_appointments(),
            desired_start,
        )
        desired_start_time = desired_start.replace(second=0)
        desired_end_time = desired_start_time + timedelta(minutes=desired_duration)

        for appointment in appointments:
            appointment_start_time = appointment.Start.replace(tzinfo=None)
            appointment_end_time = appointment.End.replace(tzinfo=None)

            if debug_level > 0:
                console.print(
                    f"Checking if desired block ({desired_start_time} - {desired_end_time}) "
                    f"collides with appointment {appointment.Subject} "
                    f"({appointment_start_time} - {appointment_end_time})",
                )

            if (
                appointment_start_time >= desired_end_time
            ):  # appointnments are sorted by Start, so it is safe to end early
                break

            if _is_colliding(
                appointment_start_time,
                appointment_end_time,
                desired_start_time,
                desired_end_time,
            ):
                return appointment

        return None


def _is_colliding(
    this_start: datetime,
    this_end: datetime,
    other_start: datetime,
    other_end: datetime,
) -> bool:
    return this_start <= other_start < this_end or this_start < other_end <= this_end
