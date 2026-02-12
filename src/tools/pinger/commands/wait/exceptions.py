class CommandWaitTimeoutError(Exception):
    """Timeout when waiting for server."""

    def __init__(
        self: "CommandWaitTimeoutError",
        message: str = "Timeout when waiting for server.",
    ) -> None:
        super().__init__(message)
