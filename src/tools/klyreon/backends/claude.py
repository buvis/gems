"""Drive Claude Code headless as a klyreon backend.

Runs ``claude -p --output-format json --json-schema <IngestPayload schema>
--tools ""`` (plus ``--model`` when configured) with the prompt on stdin, ``cwd``
set to a throwaway temp dir, and a hard ``subprocess`` timeout. ``--tools ""`` is
what enforces the no-filesystem-access half of the backend contract; the temp
cwd alone only makes vault access inconvenient. ``--json-schema`` moves shape
enforcement into the CLI, so klyreon parses the JSON envelope, takes its
``result`` field, and validates it against :class:`IngestPayload` -- a response
that still does not match is a :class:`BackendError` with ``reason="schema"``,
never a salvage attempt.

Each failure maps to its own closed reason:

- the ``claude`` binary is absent  -> ``exit`` (a clear message naming the tool)
- the subprocess exits non-zero    -> ``exit``
- the wall-clock timeout fires     -> ``timeout`` (the process is killed)
- stdout is not parseable JSON      -> ``parse``
- the payload does not match        -> ``schema``

Flags verified against ``claude --help`` on 2026-08-07 (backlog review) and
re-recorded with the known-good CLI version in the docs page; this adapter is
the one place to re-verify when the operator CLI updates.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile

from pydantic import ValidationError

from klyreon.backends.base import Backend, BackendError, BackendReason, IngestPayload

__all__ = ["ClaudeBackend"]

#: Known-good Claude CLI version at implementation time (recorded in docs too).
KNOWN_GOOD_CLI_VERSION = "claude 1.0 (flags verified 2026-08-07)"


class ClaudeBackend(Backend):
    """The ``claude`` operator adapter. Pure text-in, payload-out."""

    name = "claude"

    def __init__(self, *, model: str | None = None, timeout_cushion: int = 30) -> None:
        self.model = model
        self.timeout_cushion = timeout_cushion

    def _argv(self) -> list[str]:
        argv = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            IngestPayload.json_schema_str(),
            "--tools",
            "",
        ]
        if self.model:
            argv += ["--model", self.model]
        return argv

    def run(self, prompt: str, timeout: int) -> IngestPayload:
        """Invoke claude headless and return the validated payload."""
        if shutil.which("claude") is None:
            raise BackendError(
                BackendReason.EXIT,
                "the 'claude' CLI is not on PATH; install it or configure another backend",
            )

        argv = self._argv()
        try:
            with tempfile.TemporaryDirectory(prefix="klyreon-ingest-") as cwd:
                proc = subprocess.run(  # fixed argv, no shell; cwd is a throwaway temp dir
                    argv,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=timeout + self.timeout_cushion,
                    cwd=cwd,
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            raise BackendError(BackendReason.TIMEOUT, f"claude timed out after {timeout}s") from exc
        except OSError as exc:
            raise BackendError(BackendReason.EXIT, f"claude could not be run: {exc}") from exc

        if proc.returncode != 0:
            raise BackendError(BackendReason.EXIT, f"claude exited {proc.returncode}: {proc.stderr.strip()[:300]}")

        return self._parse_and_validate(proc.stdout)

    def _parse_and_validate(self, stdout: str) -> IngestPayload:
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise BackendError(BackendReason.PARSE, f"claude stdout is not valid JSON: {exc}") from exc

        # The envelope is Claude's --output-format json wrapper; the payload is
        # its `result` field. A bare payload (no envelope) is also accepted.
        result = envelope.get("result", envelope) if isinstance(envelope, dict) else envelope
        if isinstance(result, str):
            # Some envelopes carry the result as a JSON string; parse once more.
            try:
                result = json.loads(result)
            except json.JSONDecodeError as exc:
                raise BackendError(BackendReason.PARSE, f"claude result is not valid JSON: {exc}") from exc

        try:
            return IngestPayload.model_validate(result)
        except ValidationError as exc:
            raise BackendError(BackendReason.SCHEMA, f"claude payload does not match IngestPayload: {exc}") from exc
