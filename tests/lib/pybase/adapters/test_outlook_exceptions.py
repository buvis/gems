"""Tests for OutlookLocal exceptions (platform-independent)."""

from __future__ import annotations

import pytest

from buvis.pybase.adapters.outlook_local.exceptions import (
    OutlookAppointmentCreationFailedError,
)


class TestOutlookExceptions:
    """Tests for OutlookAppointmentCreationFailedError."""

    def test_exception_default_message(self) -> None:
        """Exception uses default message when none provided."""
        exc = OutlookAppointmentCreationFailedError()
        assert str(exc) == "Appointment not created in Outlook."

    def test_exception_custom_message(self) -> None:
        """Exception accepts custom message."""
        msg = "Custom error message"
        exc = OutlookAppointmentCreationFailedError(msg)
        assert str(exc) == msg

    def test_exception_is_exception_subclass(self) -> None:
        """Exception inherits from Exception."""
        assert issubclass(OutlookAppointmentCreationFailedError, Exception)

    def test_exception_can_be_raised_and_caught(self) -> None:
        """Exception can be raised and caught."""
        with pytest.raises(OutlookAppointmentCreationFailedError):
            raise OutlookAppointmentCreationFailedError("test")
