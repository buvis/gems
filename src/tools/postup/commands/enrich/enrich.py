"""The ``postup enrich`` command.

Turns the deterministic ``data.json`` + ``commits-digest.md`` contracts into a
schema-valid ``epics.json`` by shelling out to the ``claude`` CLI. Enrichment is
strictly optional: the flow is detect → alert → build prompt → invoke → parse →
validate → one retry (validation errors appended) → on a second failure, WARN
and continue deterministically WITHOUT writing a partial file. A missing
``data.json`` is the one hard failure — the user must run ``postup collect``
first.

Returns a :class:`CommandResult` for every outcome; the CLI adapter renders it.
No ``print``/``click.echo``/logging here, and no traceback ever reaches the
user. Availability and mode alerts ride on ``CommandResult.info`` (INFO) and
``CommandResult.warnings`` (WARN), which ``console.report_result`` renders.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from buvis.pybase.filesystem import atomic_write_text
from buvis.pybase.result import CommandResult

from postup.adapters.claude import ClaudeAdapter, ClaudeError
from postup.domain.contracts import SchemaVersionError, load_portfolio_data
from postup.domain.epics import EpicsPayload, EpicsValidationError, stable_todo_id, validate_epics
from postup.domain.prompt import build_prompt

if TYPE_CHECKING:
    from pathlib import Path

    from postup.domain.contracts import PortfolioData
    from postup.settings import PostupSettings

__all__ = ["CommandEnrich"]

_MAX_ATTEMPTS = 2  # first try + exactly one retry


class CommandEnrich:
    """Enrich the collected portfolio into a schema-valid ``epics.json``.

    Args:
        settings: Resolved postup settings (out_dir, model).
        adapter: Claude CLI adapter (injected for testing; defaults to a real
            :class:`ClaudeAdapter`).
    """

    def __init__(self, settings: PostupSettings, *, adapter: ClaudeAdapter | None = None) -> None:
        self.settings = settings
        self.adapter = adapter or ClaudeAdapter()

    def execute(self) -> CommandResult:
        """Run the enrichment pipeline and write ``epics.json`` on success.

        Returns:
            A failure result when ``data.json`` is missing or unreadable; a
            success result otherwise — enrichment never blocks the brief, so
            ``claude`` being absent or producing bad output still exits
            successfully (with warnings and no ``epics.json`` written).
        """
        out_dir = self.settings.resolved_out_dir
        data_file = out_dir / "data.json"
        if not data_file.is_file():
            return CommandResult(
                success=False,
                error=f"no data.json in {out_dir} — run 'postup collect' first",
            )
        try:
            data = load_portfolio_data(data_file)
        except (OSError, ValueError, SchemaVersionError) as exc:
            return CommandResult(success=False, error=f"unreadable data.json in {out_dir}: {exc}")

        if not self.adapter.is_available():
            return CommandResult(
                success=True,
                output=f"enrichment skipped — no epics.json written ({out_dir})",
                warnings=[
                    "claude not found — continuing deterministically; narrative, "
                    "epics, and judgment todos will be missing",
                ],
            )

        model = self.settings.model
        prompt = build_prompt(data, self._read_digest(out_dir))
        info = [f"enrichment will use claude (model: {model or 'CLI default'})"]
        return self._enrich(data, prompt, out_dir, info)

    def _read_digest(self, out_dir: Path) -> str:
        """Return the commit digest, or an empty string when it is absent."""
        digest = out_dir / "commits-digest.md"
        return digest.read_text(encoding="utf-8") if digest.is_file() else ""

    def _enrich(self, data: PortfolioData, prompt: str, out_dir: Path, info: list[str]) -> CommandResult:
        """Invoke claude with one retry, then write or degrade loudly."""
        attempt_prompt = prompt
        last_errors: list[str] = []
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                raw = self.adapter.prompt(attempt_prompt, model=self.settings.model)
            except ClaudeError as exc:
                last_errors = [str(exc)]
            else:
                try:
                    payload = validate_epics(_parse_json(raw), data)
                except EpicsValidationError as exc:
                    last_errors = exc.reasons
                else:
                    return self._write(payload, out_dir, info, invocations=attempt)
            if attempt < _MAX_ATTEMPTS:
                attempt_prompt = _append_errors(prompt, last_errors)

        return CommandResult(
            success=True,
            output=f"enrichment degraded — no epics.json written ({out_dir})",
            info=info,
            warnings=[
                "claude enrichment failed after a retry; continuing "
                f"deterministically without epics.json ({'; '.join(last_errors)})",
            ],
        )

    def _write(self, payload: EpicsPayload, out_dir: Path, info: list[str], *, invocations: int) -> CommandResult:
        """Normalize todo ids, write ``epics.json`` atomically, and report."""
        payload = _with_stable_ids(payload)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "epics.json"
        try:
            atomic_write_text(target, json.dumps(payload.model_dump(mode="json"), indent=1))
        except OSError as exc:
            return CommandResult(success=False, error=f"failed to write {target}: {exc}", info=info)
        return CommandResult(
            success=True,
            output=f"wrote {target} ({len(payload.repos)} repos, {len(payload.todos)} judgment todos)",
            info=info,
            metadata={
                "epics_json": str(target),
                "repos": len(payload.repos),
                "todos": len(payload.todos),
                "invocations": invocations,
            },
        )


def _parse_json(raw: str) -> object:
    """Parse a JSON object from a model response, tolerating surrounding text.

    A well-behaved model returns bare JSON; a chatty one may wrap it in prose or
    a markdown fence. The first balanced ``{...}`` span is extracted and parsed.

    Raises:
        EpicsValidationError: When no valid JSON object can be found.
    """
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise EpicsValidationError(["response was not valid JSON"])


def _append_errors(prompt: str, errors: list[str]) -> str:
    """Append the prior attempt's validation errors to the retry prompt."""
    joined = "\n".join(f"- {err}" for err in errors)
    return (
        f"{prompt}\n\nYour previous response was rejected for these reasons:\n"
        f"{joined}\n\nReturn a corrected JSON object that fixes every issue above."
    )


def _with_stable_ids(payload: EpicsPayload) -> EpicsPayload:
    """Return a copy whose todo ids are recomputed deterministically.

    The model is asked for stable ids but cannot be trusted to produce them, so
    every id is recomputed from ``(repo, action)``. This guarantees the
    stable-id contract regardless of what the model returned.
    """
    todos = [todo.model_copy(update={"id": stable_todo_id(todo.repo, todo.action)}) for todo in payload.todos]
    return payload.model_copy(update={"todos": todos})
