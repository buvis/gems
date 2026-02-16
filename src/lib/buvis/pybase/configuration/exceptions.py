from __future__ import annotations


class ConfigurationKeyNotFoundError(Exception):
    """Key not found in configuration exception.

    Args:
        message: Error message describing the missing key.
    """

    def __init__(
        self: ConfigurationKeyNotFoundError,
        message: str = "Key not found in configuration.",
    ) -> None:
        super().__init__(message)


class ConfigurationError(Exception):
    """Configuration loading or validation failed."""


class MissingEnvVarError(Exception):
    """Required env var not set.

    Args:
        var_names: List of missing environment variable names.

    Attributes:
        var_names: The missing variable names.
    """

    def __init__(self, var_names: list[str]) -> None:
        self.var_names = var_names
        msg = f"Missing required env vars: {', '.join(var_names)}"
        super().__init__(msg)
