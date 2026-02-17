"""Tests for OutlookLocalAdapter."""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone
from types import ModuleType
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from buvis.pybase.adapters.outlook_local.outlook_local import OutlookLocalAdapter


@pytest.fixture
def win32com_dispatch() -> MagicMock:
    """Provide a fake win32com.client.Dispatch before module import."""
    client_module = ModuleType("win32com.client")
    dispatch_mock = MagicMock()
    client_module.Dispatch = dispatch_mock

    win32com_module = ModuleType("win32com")
    win32com_module.__path__ = []
    win32com_module.client = client_module

    with patch.dict(
        sys.modules,
        {"win32com": win32com_module, "win32com.client": client_module},
    ):
        yield dispatch_mock


@pytest.fixture
def outlook_local_module(monkeypatch: pytest.MonkeyPatch, win32com_dispatch: MagicMock) -> ModuleType:
    """Import outlook_local with Windows defaults for tests."""
    sys.modules.pop("buvis.pybase.adapters.outlook_local.outlook_local", None)
    module = importlib.import_module("buvis.pybase.adapters.outlook_local.outlook_local")
    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(module, "_win32com_available", True)
    return module


@pytest.fixture
def mock_win32com(win32com_dispatch: MagicMock, outlook_local_module: ModuleType) -> MagicMock:
    """Mock win32com.client.Dispatch for COM automation."""
    mock_app = MagicMock()
    mock_namespace = MagicMock()
    mock_calendar = MagicMock()
    mock_app.GetNamespace.return_value = mock_namespace
    mock_namespace.GetDefaultFolder.return_value = mock_calendar
    win32com_dispatch.return_value = mock_app
    return win32com_dispatch


@pytest.fixture
def outlook_adapter(mock_win32com: MagicMock, outlook_local_module: ModuleType) -> OutlookLocalAdapter:
    """Create an OutlookLocalAdapter instance with mocked COM objects."""
    return outlook_local_module.OutlookLocalAdapter()


class TestOutlookLocalAdapterInit:
    """Tests for OutlookLocalAdapter initialization."""

    def test_connects_to_outlook(self, mock_win32com: MagicMock, outlook_local_module: ModuleType) -> None:
        """Init connects to Outlook via COM and gets MAPI namespace."""
        outlook_local_module.OutlookLocalAdapter()

        mock_win32com.assert_called_once_with("Outlook.Application")
        mock_app = mock_win32com.return_value
        mock_app.GetNamespace.assert_called_once_with("MAPI")
        mock_namespace = mock_app.GetNamespace.return_value
        mock_namespace.GetDefaultFolder.assert_called_once_with(9)

    def test_panics_when_dispatch_fails(self, outlook_local_module: ModuleType, win32com_dispatch: MagicMock) -> None:
        """Init calls console.panic when COM connection fails."""
        win32com_dispatch.side_effect = Exception("boom")
        with (
            patch.object(outlook_local_module.console, "panic", side_effect=SystemExit) as mock_panic,
        ):
            with pytest.raises(SystemExit):
                outlook_local_module.OutlookLocalAdapter()
            mock_panic.assert_called_once()

    def test_raises_on_non_windows(self, outlook_local_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Init raises when running on non-Windows platforms."""
        monkeypatch.setattr(outlook_local_module.os, "name", "posix")

        with pytest.raises(OSError):
            outlook_local_module.OutlookLocalAdapter()

    def test_raises_when_win32com_unavailable(
        self, outlook_local_module: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Init raises when win32com is unavailable."""
        monkeypatch.setattr(outlook_local_module, "_win32com_available", False)

        with pytest.raises(OSError):
            outlook_local_module.OutlookLocalAdapter()


class TestCreateTimeblock:
    """Tests for create_timeblock method."""

    def test_sets_properties_with_explicit_start(
        self, outlook_adapter: OutlookLocalAdapter, mock_win32com: MagicMock
    ) -> None:
        """Creates appointment with provided start time."""
        mock_app = mock_win32com.return_value
        appointment = MagicMock()
        mock_app.CreateItem.return_value = appointment

        start = datetime(2024, 3, 15, 9, 0)
        outlook_adapter.create_timeblock(
            {
                "start": start,
                "subject": "Sync",
                "body": "Align work",
                "duration": 30,
                "location": "Desk",
                "categories": "Work",
            }
        )

        assert appointment.Start is start
        assert appointment.Subject == "Sync"
        assert appointment.Body == "Align work"
        assert appointment.Duration == 30
        assert appointment.Location == "Desk"
        assert appointment.Categories == "Work"
        appointment.Save.assert_called_once()

    def test_uses_current_time_when_start_missing(
        self,
        outlook_adapter: OutlookLocalAdapter,
        mock_win32com: MagicMock,
        outlook_local_module: ModuleType,
    ) -> None:
        """Uses current hour when start time not provided."""

        mock_app = mock_win32com.return_value
        appointment = MagicMock()
        mock_app.CreateItem.return_value = appointment

        fake_now = datetime(2024, 3, 15, 9, 37, 22, tzinfo=timezone.utc)
        expected_start = fake_now.replace(minute=0, second=0)

        with (
            patch.object(
                outlook_local_module.tzlocal,
                "get_localzone",
                return_value=timezone.utc,
            ),
            patch.object(outlook_local_module, "datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value = fake_now
            outlook_adapter.create_timeblock(
                {
                    "subject": "Sync",
                    "body": "Align work",
                    "duration": 30,
                    "location": "Desk",
                    "categories": "Work",
                }
            )

        assert appointment.Start == expected_start
        appointment.Save.assert_called_once()

    def test_raises_on_save_failure(self, outlook_adapter: OutlookLocalAdapter, mock_win32com: MagicMock) -> None:
        """Raises OutlookAppointmentCreationFailedError when save fails."""
        from buvis.pybase.adapters.outlook_local.exceptions import (
            OutlookAppointmentCreationFailedError,
        )

        mock_app = mock_win32com.return_value
        appointment = MagicMock()
        appointment.Save.side_effect = Exception("boom")
        mock_app.CreateItem.return_value = appointment

        with pytest.raises(OutlookAppointmentCreationFailedError) as excinfo:
            outlook_adapter.create_timeblock(
                {
                    "start": datetime(2024, 3, 15, 9, 0),
                    "subject": "Sync",
                    "body": "Align work",
                    "duration": 30,
                    "location": "Desk",
                    "categories": "Work",
                }
            )

        assert "Appointment creation failed" in str(excinfo.value)


class TestGetAppointments:
    """Tests for appointment retrieval methods."""

    def test_get_all_appointments_includes_recurrences(self, outlook_adapter: OutlookLocalAdapter) -> None:
        """Returns calendar items with recurrences included and sorted."""
        items = MagicMock()
        outlook_adapter.calendar.Items = items

        result = outlook_adapter.get_all_appointments()

        assert result is items
        assert items.IncludeRecurrences is True
        items.Sort.assert_called_once_with("[Start]")

    def test_get_day_appointments_filters_by_date(self, outlook_adapter: OutlookLocalAdapter) -> None:
        """Restricts appointments to specified date."""
        appointments = MagicMock()

        matching = MagicMock()
        matching.Start = datetime(2024, 3, 15, 9, 0)

        non_matching = MagicMock()
        non_matching.Start = datetime(2024, 3, 16, 9, 0)

        appointments.Restrict.return_value = [matching, non_matching]
        date = datetime(2024, 3, 15, 12, 0)

        result = outlook_adapter.get_day_appointments(appointments, date)

        assert result == [matching]
        appointments.Restrict.assert_called_once_with("[Start] >= '2024-03-15' AND [End] <= '2024-03-16'")


class TestGetConflictingAppointment:
    """Tests for conflict detection."""

    def test_returns_conflicting_appointment(
        self, outlook_adapter: OutlookLocalAdapter, outlook_local_module: ModuleType
    ) -> None:
        """Returns appointment that conflicts with desired time slot."""
        appointment = MagicMock()
        appointment.Start = datetime(2024, 3, 15, 9, 30)
        appointment.End = datetime(2024, 3, 15, 10, 30)
        appointment.Subject = "Busy"

        desired_start = datetime(2024, 3, 15, 10, 0)

        with (
            patch.object(outlook_adapter, "get_all_appointments", return_value=MagicMock()),
            patch.object(outlook_adapter, "get_day_appointments", return_value=[appointment]),
            patch.object(outlook_local_module.console, "print"),
        ):
            result = outlook_adapter.get_conflicting_appointment(desired_start, 60, debug_level=1)

        assert result is appointment

    def test_returns_none_when_free(self, outlook_adapter: OutlookLocalAdapter) -> None:
        """Returns None when no conflicts exist."""
        appointment = MagicMock()
        appointment.Start = datetime(2024, 3, 15, 12, 0)
        appointment.End = datetime(2024, 3, 15, 13, 0)

        desired_start = datetime(2024, 3, 15, 10, 0)

        with (
            patch.object(outlook_adapter, "get_all_appointments", return_value=MagicMock()),
            patch.object(outlook_adapter, "get_day_appointments", return_value=[appointment]),
        ):
            result = outlook_adapter.get_conflicting_appointment(desired_start, 60)

        assert result is None


class TestIsColliding:
    """Tests for _is_colliding helper function."""

    def test_detects_overlap(self, outlook_local_module: ModuleType) -> None:
        """Returns True when time ranges overlap."""
        assert outlook_local_module._is_colliding(
            datetime(2024, 3, 15, 9, 0),
            datetime(2024, 3, 15, 10, 0),
            datetime(2024, 3, 15, 9, 30),
            datetime(2024, 3, 15, 9, 45),
        )

    def test_detects_no_overlap(self, outlook_local_module: ModuleType) -> None:
        """Returns False when time ranges don't overlap."""
        assert not outlook_local_module._is_colliding(
            datetime(2024, 3, 15, 9, 0),
            datetime(2024, 3, 15, 10, 0),
            datetime(2024, 3, 15, 10, 0),
            datetime(2024, 3, 15, 11, 0),
        )
