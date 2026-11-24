"""The shared LLM backend contract: request in, schema-validated payload out.

Nothing here prints, logs or exits; failures are raised as
:class:`BackendError` (operational) or :class:`LLMConfigError` (configuration).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import IO, TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, RootModel, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "MAX_REPLY_BYTES",
    "MAX_STDERR_BYTES",
    "Backend",
    "BackendError",
    "BackendReason",
    "JsonObject",
    "LLMConfigError",
    "LLMRequest",
    "SchemaT",
    "parse_json_text",
    "require_strict_schema",
    "run_cli",
    "validate_payload",
    "wire_schema",
]

MAX_REPLY_BYTES = 4 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024


class BackendReason(str, Enum):
    """Closed set of reasons a backend call can fail."""

    TIMEOUT = "timeout"
    EXIT = "exit"
    PARSE = "parse"
    SCHEMA = "schema"


class BackendError(RuntimeError):
    """A backend call failed, with a closed ``reason`` and a human ``detail``.

    Args:
        reason: A :class:`BackendReason` or its value; an unknown string raises ``ValueError``.
        detail: Free-text diagnostic.
        backend: Registry name of the backend that failed.
    """

    def __init__(self, reason: BackendReason | str, detail: str, *, backend: str) -> None:
        self.reason = BackendReason(reason)
        self.detail = detail
        self.backend = backend
        super().__init__(f"[{self.reason.value}] {backend}: {detail}")


class LLMConfigError(ValueError):
    """Unknown backend name, unattended refusal, or a schema type that does not forbid extra keys."""


@dataclass(frozen=True)
class LLMRequest:
    """One prompt, with an optional system text."""

    prompt: str
    system: str | None = None

    def as_text(self) -> str:
        """Return the request as one text (the stdin for CLI backends)."""
        if self.system is None:
            return self.prompt
        return f"{self.system}\n\n{self.prompt}"


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class JsonObject(RootModel[dict[str, Any]]):
    """Any JSON object. For callers (doc) that coerce fields themselves."""


@runtime_checkable
class Backend(Protocol):
    """The interface every LLM adapter implements."""

    name: str
    unattended_safe: bool

    def complete(
        self, request: LLMRequest, schema: type[SchemaT], *, timeout: float, model: str | None = None
    ) -> SchemaT:
        """Return the reply validated against ``schema``, or raise ``BackendError``."""
        ...


def wire_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Return the JSON schema sent to the backend for ``schema``."""
    if issubclass(schema, JsonObject):
        return {"type": "object"}
    return schema.model_json_schema()


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _find_open_object(node: Any, pointer: str) -> str | None:
    """Return the JSON pointer of the first object node that allows extra keys."""
    if not isinstance(node, dict):
        return None
    if "properties" in node and node.get("additionalProperties") is not False:
        return pointer
    children: list[tuple[str, Any]] = []
    for key in ("$defs", "properties"):
        children += [(f"{pointer}/{key}/{_escape(name)}", sub) for name, sub in node.get(key, {}).items()]
    for key in ("items", "additionalProperties"):
        if isinstance(node.get(key), dict):
            children.append((f"{pointer}/{key}", node[key]))
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        children += [(f"{pointer}/{key}/{index}", sub) for index, sub in enumerate(node.get(key, []))]
    for child_pointer, child in children:
        found = _find_open_object(child, child_pointer)
        if found is not None:
            return found
    return None


def require_strict_schema(schema: type[BaseModel]) -> None:
    """Raise ``LLMConfigError`` unless every object in ``schema`` forbids extra keys.

    ``JsonObject`` and its subclasses are accepted as is. An explicit
    ``dict[str, X]`` field is an open mapping and allowed.
    """
    if issubclass(schema, JsonObject):
        return
    found = _find_open_object(schema.model_json_schema(), "#")
    if found is not None:
        msg = f"schema {schema.__name__} allows unexpected keys at {found}; set extra='forbid'"
        raise LLMConfigError(msg)


def parse_json_text(text: object, *, backend: str) -> Any:
    """Parse reply text as one JSON document, or raise a ``parse`` ``BackendError``.

    A non-string ``text`` (a null ``content``, or bytes, which ``json.loads`` would accept) is a parse error.
    """
    if not isinstance(text, str):
        detail = f"reply is not valid JSON: expected text, got {type(text).__name__}"
        raise BackendError(BackendReason.PARSE, detail, backend=backend)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BackendError(BackendReason.PARSE, f"reply is not valid JSON: {exc}", backend=backend) from exc


def validate_payload(schema: type[SchemaT], data: Any, *, backend: str) -> SchemaT:
    """Validate ``data`` against ``schema``, or raise a ``schema`` ``BackendError``."""
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        detail = f"reply does not match {schema.__name__}: {exc}"
        raise BackendError(BackendReason.SCHEMA, detail, backend=backend) from exc


def _kill_group(pid: int) -> None:
    """Kill the CLI's whole process group; a group that is already gone is fine."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _feed(stream: IO[bytes], data: bytes, errors: list[OSError]) -> None:
    """Write ``data`` to the CLI's stdin and close it; a closed pipe is left to the exit code."""
    try:
        with stream:
            stream.write(data)
    except BrokenPipeError:
        pass
    except OSError as exc:
        errors.append(exc)


def _drain(
    stream: IO[bytes], buf: bytearray, cap: int, errors: list[OSError], on_overflow: Callable[[], None] | None
) -> None:
    """Read ``stream`` into ``buf`` up to ``cap`` bytes.

    With ``on_overflow``, more than ``cap`` bytes calls it and stops reading;
    without it, bytes past ``cap`` are read and discarded.
    """
    try:
        with stream:
            while chunk := stream.read(8192):
                room = cap - len(buf)
                if len(chunk) > room and on_overflow is not None:
                    on_overflow()
                    return
                buf += chunk[:room]
    except OSError as exc:
        errors.append(exc)


def _spawn(argv: list[str], cwd: str, backend: str) -> subprocess.Popen[bytes]:
    try:
        return subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            start_new_session=True,
        )
    except OSError as exc:
        raise BackendError(BackendReason.EXIT, str(exc), backend=backend) from exc


def _wait(proc: subprocess.Popen[bytes], timeout: float) -> bool:
    """Wait for the CLI; on a timeout kill its process group. Return whether it timed out."""
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc.pid)
        proc.wait()
        return True
    return False


def _run(argv: list[str], data: bytes, cwd: str, *, timeout: float, backend: str) -> str:
    proc = _spawn(argv, cwd, backend)
    out, err, errors, overflow = bytearray(), bytearray(), list[OSError](), threading.Event()

    def stop_on_overflow() -> None:
        overflow.set()
        _kill_group(proc.pid)

    threading.Thread(target=_feed, args=(proc.stdin, data, errors), daemon=True).start()
    readers = [
        threading.Thread(target=_drain, args=(proc.stdout, out, MAX_REPLY_BYTES, errors, stop_on_overflow)),
        threading.Thread(target=_drain, args=(proc.stderr, err, MAX_STDERR_BYTES, errors, None)),
    ]
    for reader in readers:
        reader.daemon = True
        reader.start()
    try:
        timed_out = _wait(proc, timeout)
    finally:
        _kill_group(proc.pid)
        proc.wait()
    deadline = time.monotonic() + 5.0
    for reader in readers:
        reader.join(timeout=max(0.0, deadline - time.monotonic()))
    excerpt = bytes(err).decode("utf-8", errors="replace").strip()[:300]
    if timed_out:
        raise BackendError(BackendReason.TIMEOUT, f"no reply within {timeout} seconds", backend=backend)
    if any(reader.is_alive() for reader in readers):
        raise BackendError(BackendReason.EXIT, "output pipe still open after exit", backend=backend)
    if overflow.is_set():
        raise BackendError(BackendReason.EXIT, f"output larger than {MAX_REPLY_BYTES} bytes", backend=backend)
    if errors:
        raise BackendError(BackendReason.EXIT, f"pipe error: {errors[0]}", backend=backend)
    if proc.returncode != 0:
        raise BackendError(BackendReason.EXIT, f"exited with code {proc.returncode}: {excerpt}", backend=backend)
    try:
        return bytes(out).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BackendError(BackendReason.PARSE, f"output is not UTF-8: {exc}", backend=backend) from exc


def run_cli(argv: list[str], stdin_text: str, *, timeout: float, backend: str) -> str:
    """Run a CLI with ``stdin_text`` on stdin and return its stdout.

    The CLI runs without a shell, in its own session and in a fresh temp dir that is removed on
    every exit path. Its whole process group is killed after it exits, on a timeout, on output
    past ``MAX_REPLY_BYTES`` and on any exception (which is then re-raised).

    Args:
        argv: The command and its arguments, passed literally.
        stdin_text: Text sent to the CLI as UTF-8 on stdin.
        timeout: Seconds to wait for the CLI to exit.
        backend: Registry name used in errors.

    Returns:
        The decoded stdout of a zero-exit run.

    Raises:
        BackendError: ``exit`` for a missing executable, a bad prompt, a spawn or pipe error,
            oversized output or a non-zero exit; ``timeout``; ``parse`` for non-UTF-8 output.
    """
    if shutil.which(argv[0]) is None:
        raise BackendError(BackendReason.EXIT, f"{argv[0]!r} is not on PATH", backend=backend)
    try:
        data = stdin_text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BackendError(BackendReason.EXIT, "prompt is not valid UTF-8", backend=backend) from exc
    with tempfile.TemporaryDirectory(prefix="bim-llm-") as cwd:
        return _run(argv, data, cwd, timeout=timeout, backend=backend)
