import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter


@pytest.fixture
def shell_adapter() -> ShellAdapter:
    """Create a ShellAdapter instance for testing."""
    return ShellAdapter()


@pytest.fixture
def shell_adapter_no_logging() -> ShellAdapter:
    """Create a ShellAdapter instance with logging suppressed."""
    return ShellAdapter(suppress_logging=True)


class TestShellAdapterInit:
    """Test ShellAdapter initialization."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        adapter = ShellAdapter()
        assert adapter.aliases == {}
        assert adapter.is_logging is True

    def test_init_suppress_logging(self) -> None:
        """Test initialization with logging suppressed."""
        adapter = ShellAdapter(suppress_logging=True)
        assert adapter.aliases == {}
        assert adapter.is_logging is False


class TestShellAdapterAlias:
    """Test alias functionality."""

    def test_alias_simple(self, shell_adapter: ShellAdapter) -> None:
        """Test setting a simple alias."""
        shell_adapter.alias("ll", "ls -la")
        assert shell_adapter.aliases["ll"] == "ls -la"

    def test_alias_multiple(self, shell_adapter: ShellAdapter) -> None:
        """Test setting multiple aliases."""
        shell_adapter.alias("ll", "ls -la")
        shell_adapter.alias("la", "ls -A")
        assert shell_adapter.aliases["ll"] == "ls -la"
        assert shell_adapter.aliases["la"] == "ls -A"

    def test_alias_override(self, shell_adapter: ShellAdapter) -> None:
        """Test overriding an existing alias."""
        shell_adapter.alias("ll", "ls -la")
        shell_adapter.alias("ll", "ls -l")
        assert shell_adapter.aliases["ll"] == "ls -l"


class TestShellAdapterExpandAlias:
    """Test alias expansion functionality."""

    def test_expand_alias_exact_match(self, shell_adapter: ShellAdapter) -> None:
        """Test expanding an alias that matches exactly."""
        shell_adapter.alias("ll", "ls -la")
        result = shell_adapter._expand_alias("ll")
        assert result == "ls -la"

    def test_expand_alias_prefix_match(self, shell_adapter: ShellAdapter) -> None:
        """Test expanding an alias that is a prefix."""
        shell_adapter.alias("ll", "ls -la")
        result = shell_adapter._expand_alias("ll /tmp")
        assert result == "ls -la /tmp"

    def test_expand_alias_no_match(self, shell_adapter: ShellAdapter) -> None:
        """Test that commands without aliases are unchanged."""
        shell_adapter.alias("ll", "ls -la")
        result = shell_adapter._expand_alias("pwd")
        assert result == "pwd"

    def test_expand_alias_partial_match(self, shell_adapter: ShellAdapter) -> None:
        """Test that partial matches get expanded (current behavior)."""
        shell_adapter.alias("ll", "ls -la")
        result = shell_adapter._expand_alias("llama")
        assert result == "ls -laama"

    def test_expand_alias_empty_command(self, shell_adapter: ShellAdapter) -> None:
        """Test expanding an empty command."""
        result = shell_adapter._expand_alias("")
        assert result == ""


class TestShellAdapterExpandEnvironmentVariables:
    """Test environment variable expansion."""

    @patch.dict(os.environ, {"TEST_VAR": "test_value"})
    def test_expand_env_var_simple(self, shell_adapter: ShellAdapter) -> None:
        """Test expanding a simple environment variable."""
        result = shell_adapter._expand_environment_variables("echo $TEST_VAR")
        assert result == "echo test_value"

    @patch.dict(os.environ, {"HOME": "/home/user"})
    def test_expand_env_var_braces(self, shell_adapter: ShellAdapter) -> None:
        """Test expanding environment variables with braces."""
        result = shell_adapter._expand_environment_variables("cd ${HOME}/documents")
        assert result == "cd /home/user/documents"

    def test_expand_env_var_nonexistent(self, shell_adapter: ShellAdapter) -> None:
        """Test expanding non-existent environment variables."""
        result = shell_adapter._expand_environment_variables("echo $NONEXISTENT_VAR")
        # Should leave the variable unexpanded or empty based on os.path.expandvars behavior
        assert "$NONEXISTENT_VAR" in result or result == "echo "

    def test_expand_env_var_no_variables(self, shell_adapter: ShellAdapter) -> None:
        """Test command with no environment variables."""
        result = shell_adapter._expand_environment_variables("echo hello")
        assert result == "echo hello"


class TestShellAdapterExe:
    """Test command execution functionality."""

    @patch("subprocess.run")
    def test_exe_successful_command(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test executing a successful command."""
        mock_result = Mock()
        mock_result.stdout = "Hello World"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        stderr, stdout = shell_adapter.exe("echo 'Hello World'", None)

        assert stdout == "Hello World"
        assert stderr == ""
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_exe_command_with_stderr(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test executing a command that produces stderr output."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = "Warning message"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        stderr, stdout = shell_adapter.exe("some_command", None)

        assert stdout == ""
        assert stderr == ""

    @patch("subprocess.run")
    def test_exe_failed_command(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test executing a failed command."""
        error = subprocess.CalledProcessError(1, "false", "output", "error")
        mock_run.side_effect = error

        stderr, stdout = shell_adapter.exe("false", None)

        assert stderr == "error"
        assert stdout == ""

    @patch("subprocess.run")
    def test_exe_with_working_directory(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test executing a command with a valid working directory."""
        mock_result = Mock()
        mock_result.stdout = "success"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        working_dir = Path("/tmp")

        with patch.object(Path, "is_dir", return_value=True):
            stderr, stdout = shell_adapter.exe("pwd", working_dir)

        call_args = mock_run.call_args
        assert call_args[1]["cwd"] == working_dir

    @patch("subprocess.run")
    def test_exe_with_invalid_working_directory(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test executing a command with a nonexistent working directory falls back to cwd."""
        mock_result = Mock()
        mock_result.stdout = "success"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        working_dir = Path("/nonexistent")

        stderr, stdout = shell_adapter.exe("pwd", working_dir)

        call_args = mock_run.call_args
        assert call_args[1]["cwd"] == Path.cwd()

    @patch("subprocess.run")
    def test_exe_expands_aliases(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test that exe expands aliases before execution."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        shell_adapter.alias("ll", "ls -la")
        shell_adapter.exe("ll", None)

        # Check that the expanded command was passed to subprocess.run
        call_args = mock_run.call_args
        assert call_args[0][0] == "ls -la"

    @patch("subprocess.run")
    @patch.dict(os.environ, {"TEST_VAR": "test_value"})
    def test_exe_expands_env_vars(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test that exe expands environment variables before execution."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        shell_adapter.exe("echo $TEST_VAR", None)

        # Check that the expanded command was passed to subprocess.run
        call_args = mock_run.call_args
        assert call_args[0][0] == "echo test_value"

    @patch("subprocess.run")
    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_exe_logging_enabled(
        self,
        mock_console: Mock,
        mock_run: Mock,
    ) -> None:
        """Test that logging works when enabled."""
        adapter = ShellAdapter(suppress_logging=False)

        mock_result = Mock()
        mock_result.stdout = "stdout content"
        mock_result.stderr = "stderr content"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        adapter.exe("echo test", None)

        mock_console.info.assert_called_once_with("stdout content")
        mock_console.warning.assert_called_once_with("stderr content")

    @patch("subprocess.run")
    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_exe_logging_disabled(
        self,
        mock_console: Mock,
        mock_run: Mock,
    ) -> None:
        """Test that logging is disabled when suppress_logging=True."""
        adapter = ShellAdapter(suppress_logging=True)

        mock_result = Mock()
        mock_result.stdout = "stdout content"
        mock_result.stderr = "stderr content"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        adapter.exe("echo test", None)

        mock_console.info.assert_not_called()
        mock_console.warning.assert_not_called()


class TestShellAdapterInteract:
    """Test interactive command functionality."""

    @patch("subprocess.run")
    def test_interact_simple_session(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test a simple interactive session."""
        shell_adapter.interact("python", None)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == "python"
        assert call_args[1]["shell"] is True
        assert call_args[1]["check"] is False

    @patch("subprocess.run")
    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_interact_os_error(
        self,
        mock_console: Mock,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test interactive session with OSError."""
        mock_run.side_effect = OSError("Test error")

        shell_adapter.interact("python", None)

        mock_console.failure.assert_called_once_with("An error occurred")

    @patch("subprocess.run")
    def test_interact_with_working_directory(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test interactive session with valid working directory."""
        working_dir = Path("/tmp")
        with patch.object(Path, "is_dir", return_value=True):
            shell_adapter.interact("python", working_dir)

        call_args = mock_run.call_args
        assert call_args[1]["cwd"] == working_dir

    @patch("subprocess.run")
    def test_interact_expands_aliases(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test that interact expands aliases."""
        shell_adapter.alias("py", "python3")
        shell_adapter.interact("py", None)

        call_args = mock_run.call_args
        assert call_args[0][0] == "python3"


class TestShellAdapterIsCommandAvailable:
    """Test command availability checking."""

    @patch("shutil.which")
    def test_is_command_available_true(
        self,
        mock_which: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test checking for an available command."""
        mock_which.return_value = "/usr/bin/python"
        result = shell_adapter.is_command_available("python")
        assert result is True
        mock_which.assert_called_once_with("python")

    @patch("shutil.which")
    def test_is_command_available_false(
        self,
        mock_which: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test checking for an unavailable command."""
        mock_which.return_value = None
        result = shell_adapter.is_command_available("nonexistent_command")
        assert result is False
        mock_which.assert_called_once_with("nonexistent_command")


class TestShellAdapterLogging:
    """Test logging functionality."""

    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_log_normal_output_both(
        self,
        mock_console: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test logging both stdout and stderr."""
        shell_adapter._log_normal_output("stdout content", "stderr content")
        mock_console.info.assert_called_once_with("stdout content")
        mock_console.warning.assert_called_once_with("stderr content")

    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_log_normal_output_stdout_only(
        self,
        mock_console: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test logging only stdout."""
        shell_adapter._log_normal_output("stdout content", None)
        mock_console.info.assert_called_once_with("stdout content")
        mock_console.warning.assert_not_called()

    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_log_normal_output_stderr_only(
        self,
        mock_console: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test logging only stderr."""
        shell_adapter._log_normal_output(None, "stderr content")
        mock_console.info.assert_not_called()
        mock_console.warning.assert_called_once_with("stderr content")

    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_log_normal_output_neither(
        self,
        mock_console: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test logging when both outputs are None."""
        shell_adapter._log_normal_output(None, None)
        mock_console.info.assert_not_called()
        mock_console.warning.assert_not_called()

    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_log_error_output(
        self,
        mock_console: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test logging error output."""
        error = subprocess.CalledProcessError(1, "false", "stdout", "stderr")
        shell_adapter._log_error_output(error)

        assert mock_console.failure.call_count == 3
        mock_console.failure.assert_any_call("Command failed with return code 1")
        mock_console.failure.assert_any_call("STDOUT: stdout")
        mock_console.failure.assert_any_call("STDERR: stderr")

    @patch("buvis.pybase.adapters.shell.shell.console")
    def test_log_error_output_no_output(
        self,
        mock_console: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test logging error output when stdout/stderr are None."""
        error = subprocess.CalledProcessError(1, "false", None, None)
        shell_adapter._log_error_output(error)

        # Should only log the return code
        mock_console.failure.assert_called_once_with("Command failed with return code 1")


class TestShellAdapterIntegration:
    """Integration tests combining multiple features."""

    @patch("subprocess.run")
    def test_full_command_processing(
        self,
        mock_run: Mock,
        shell_adapter: ShellAdapter,
    ) -> None:
        """Test complete command processing with aliases and env vars."""
        mock_result = Mock()
        mock_result.stdout = "processed output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Set up alias and environment variable
        shell_adapter.alias("test_cmd", "echo $TEST_VAR")

        with patch.dict(os.environ, {"TEST_VAR": "hello"}):
            stderr, stdout = shell_adapter.exe("test_cmd", None)

        assert stdout == "processed output"
        assert stderr == ""

        # Verify the command was properly expanded
        call_args = mock_run.call_args
        assert call_args[0][0] == "echo hello"

    def test_multiple_aliases_chaining(self, shell_adapter: ShellAdapter) -> None:
        """Test that only the first matching alias is expanded."""
        shell_adapter.alias("a", "b")
        shell_adapter.alias("b", "c")

        # Should only expand 'a' to 'b', not chain to 'c'
        result = shell_adapter._expand_alias("a")
        assert result == "b"
