"""Claude CLI (``claude``) delegation — the only LLM path in postup.

Mirrors :class:`postup.adapters.gh.GhAdapter`: a thin subprocess shell-out with
no business logic. :meth:`ClaudeAdapter.is_available` is a cheap presence check
run before any prompt is built; :meth:`ClaudeAdapter.prompt` runs ``claude -p``
headlessly and returns the raw response. A non-zero exit, a timeout, or empty
output raises :class:`ClaudeError` so the command layer can apply the
retry-once-then-degrade rule.

No cloud AI SDK and no new Python dependency: the ``claude`` binary on ``PATH``
is the entire integration surface.
"""

from __future__ import annotations

import shutil
import subprocess

__all__ = ["ClaudeAdapter", "ClaudeError"]

_CLAUDE_TIMEOUT = 300


class ClaudeError(RuntimeError):
    """Raised when a ``claude`` subprocess fails or produces unusable output."""


class ClaudeAdapter:
    """Detect and invoke the ``claude`` CLI for headless enrichment."""

    def is_available(self) -> bool:
        """Return whether the ``claude`` binary is resolvable on ``PATH``.

        Returns:
            ``True`` when ``claude`` is found, ``False`` otherwise. Absence is a
            degradation path, never an error.
        """
        return shutil.which("claude") is not None

    def prompt(self, text: str, *, model: str | None = None, timeout: int = _CLAUDE_TIMEOUT) -> str:
        """Run ``claude -p <text>`` and return the raw response text.

        The ``--model`` flag is passed only when ``model`` is set; when it is
        ``None`` the ``claude`` CLI's own default model is used (per the PRD's
        inherit-CLI-default decision), so postup never pins a model.

        Args:
            text: The full prompt to send.
            model: Optional model name; omitted from the argv when ``None``.
            timeout: Seconds before the subprocess is killed.

        Returns:
            The model's stdout, stripped of trailing whitespace.

        Raises:
            ClaudeError: On a missing binary, timeout, non-zero exit, or empty
                output.
        """
        args = ["claude", "-p", text]
        if model:
            args += ["--model", model]
        try:
            proc = subprocess.run(  # fixed argv, no shell
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ClaudeError(f"claude -p: {exc}") from exc
        if proc.returncode != 0:
            raise ClaudeError(f"claude -p: {proc.stderr.strip()[:300]}")
        output = proc.stdout.strip()
        if not output:
            raise ClaudeError("claude -p: empty response")
        return output
