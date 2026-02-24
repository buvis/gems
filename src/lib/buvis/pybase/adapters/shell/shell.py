from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from buvis.pybase.adapters.console import console


class ShellAdapter:
    """
    A class for executing shell commands and logging their output,
    with support for command aliases and environment variables.

    It executes shell commands, logs the output, and handles errors.
    """

    def __init__(self: ShellAdapter, *, suppress_logging: bool = False) -> None:
        """
        Initialize the ShellCommandExecutor and set up the logger.
        """
        self.aliases: dict[str, str] = {}
        self.is_logging = not suppress_logging

    def alias(self: ShellAdapter, alias: str, command: str) -> None:
        """Define a command alias.

        Args:
            alias: The alias name to define.
            command: The command string that the alias maps to.
        """
        self.aliases[alias] = command

    def exe(
        self: ShellAdapter,
        command: str,
        working_dir: Path | None,
    ) -> tuple[str, str]:
        """
        Execute a shell command and log its output.

        This method runs the given command, logs stdout as info and stderr as error.
        If the command fails, it logs both stdout and stderr.

        Args:
            command: A string representing the command to execute.
            working_dir: Path to directory where the command will be executed.
        Returns:
            A tuple of (stderr, stdout) from command execution. On failure, returns
            (error_message, empty string).
        """
        expanded_command = self._expand_alias(command)
        expanded_command = self._expand_environment_variables(expanded_command)

        cwd = Path(working_dir) if working_dir and Path(working_dir).is_dir() else Path.cwd()

        try:
            result = subprocess.run(  # noqa: S602 - shell=True required for alias/env expansion
                expanded_command,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=os.environ.copy(),
            )
            if self.is_logging:
                self._log_normal_output(result.stdout, result.stderr)
        except subprocess.CalledProcessError as e:
            if self.is_logging:
                self._log_error_output(e)
            detail = e.stderr.strip() if e.stderr else str(e)
            return detail, ""
        else:
            return "", result.stdout

    def interact(
        self: ShellAdapter,
        command: str,
        working_dir: Path | None,
    ) -> None:
        expanded_command = self._expand_alias(command)
        expanded_command = self._expand_environment_variables(expanded_command)

        cwd = Path(working_dir) if working_dir and Path(working_dir).is_dir() else Path.cwd()

        try:
            subprocess.run(  # noqa: S602
                expanded_command,
                shell=True,
                check=False,
                cwd=cwd,
                env=os.environ.copy(),
            )
        except OSError:
            console.failure("An error occurred")

    def is_command_available(self: ShellAdapter, command: str) -> bool:
        """
        Check if a given command is available in the system PATH.

        Args:
            command: The name of the command to check.

        Returns:
            True if the command exists, False otherwise.
        """
        return shutil.which(command) is not None

    def _expand_alias(self: ShellAdapter, command: str) -> str:
        """Expand aliases in the command string.

        Args:
            command: The command string potentially containing aliases.

        Returns:
            The command string with any aliases expanded.
        """
        for alias, cmd in self.aliases.items():
            if command.startswith(alias):
                return command.replace(alias, cmd, 1)
        return command

    def _expand_environment_variables(self: ShellAdapter, command: str) -> str:
        """Expand environment variables in the command string.

        Args:
            command: The command string potentially containing environment variables in ${VAR} format.

        Returns:
            The command string with environment variables expanded.
        """
        return os.path.expandvars(command)

    def _log_normal_output(
        self: ShellAdapter,
        stdout: str | None,
        stderr: str | None,
    ) -> None:
        """Log the successful output of a command.

        Args:
            stdout: The standard output of the command.
            stderr: The standard error output of the command.
        """
        if stdout:
            console.info(stdout)
        if stderr:
            console.warning(stderr)

    def _log_error_output(self: ShellAdapter, e: subprocess.CalledProcessError) -> None:
        """Log the error output of a failed command execution.

        Args:
            e: The exception raised for the failed command execution.
        """
        console.failure(f"Command failed with return code {e.returncode}")
        if e.stdout:
            console.failure(f"STDOUT: {e.stdout}")
        if e.stderr:
            console.failure(f"STDERR: {e.stderr}")
