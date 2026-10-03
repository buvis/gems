"""The ingest prompt ships inside the package and loads via importlib.resources.

The loop never depends on files installed into an operator's home directory
(PRD "Prompt library"). ``assemble_prompt`` fills the ``ingest.md`` template
with the source, the voice, the split rule ceiling, the claim set, and the
response schema, and returns one string.

When ``<root>/voice.md`` is absent, :data:`DEFAULT_VOICE` is used and the
caller is told to warn (``assemble_prompt`` returns the warning alongside the
prompt rather than printing it, keeping this module console-free).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from klyreon.backends.base import IngestPayload

__all__ = ["DEFAULT_VOICE", "assemble_prompt", "load_template", "load_voice"]

#: Built-in voice used when the vault has no ``voice.md`` (PRD "Prompt library").
DEFAULT_VOICE = (
    "Write in clear, direct, declarative prose. Paraphrase the source into the "
    "vault's own voice; never copy its wording. Prefer short sentences and "
    "concrete nouns. State claims plainly without hedging. Second person is "
    "avoided; write about the idea, not the reader."
)

_TEMPLATE_RESOURCE = "ingest.md"


def load_template() -> str:
    """Return the raw ``ingest.md`` template text from package data."""
    return resources.files(__package__).joinpath(_TEMPLATE_RESOURCE).read_text(encoding="utf-8")


def load_voice(root: Path) -> tuple[str, str | None]:
    """Return ``(voice_text, warning)``.

    Reads ``<root>/voice.md`` when present; otherwise returns
    :data:`DEFAULT_VOICE` and a warning string the caller should surface.
    """
    voice_file = root / "voice.md"
    if voice_file.is_file():
        text = voice_file.read_text(encoding="utf-8").strip()
        if text:
            return text, None
    return DEFAULT_VOICE, f"no voice.md at {voice_file}; using the built-in default voice"


def assemble_prompt(
    *,
    source_text: str,
    source_archive_path: str,
    claim_set: str,
    voice: str,
    max_body_lines: int,
) -> str:
    """Fill the ingest template with everything the backend needs in one string.

    The response schema is the live :class:`IngestPayload` JSON Schema, so the
    prompt and the ``--json-schema`` the adapter feeds the CLI are the same
    contract (PRD "Prompt library": schema reaches the prompt).
    """
    template = load_template()
    return template.format(
        voice=voice,
        max_body_lines=max_body_lines,
        claim_set=claim_set,
        source_archive_path=source_archive_path,
        source_text=source_text,
        response_schema=IngestPayload.json_schema_str(),
    )
