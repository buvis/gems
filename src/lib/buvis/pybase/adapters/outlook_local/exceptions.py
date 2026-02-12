class OutlookAppointmentCreationFailedError(Exception):
    """Appointment creation failed in Outlook exception."""

    def __init__(
        self: "OutlookAppointmentCreationFailedError",
        message: str = "Appointment not created in Outlook.",
    ) -> None:
        super().__init__(message)
