"""Phase 0: the prompt library (loader, default voice, assembly)."""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.prompts import DEFAULT_VOICE, assemble_prompt, load_template, load_voice

pytestmark = pytest.mark.klyreon


class TestVoice:
    def test_present_voice_file_is_read(self, tmp_path: Path) -> None:
        (tmp_path / "voice.md").write_text("Terse and declarative.\n", encoding="utf-8")
        voice, warning = load_voice(tmp_path)
        assert voice == "Terse and declarative."
        assert warning is None

    def test_missing_voice_falls_back_and_warns(self, tmp_path: Path) -> None:
        voice, warning = load_voice(tmp_path)
        assert voice == DEFAULT_VOICE
        assert warning is not None
        assert "voice.md" in warning

    def test_empty_voice_file_falls_back(self, tmp_path: Path) -> None:
        (tmp_path / "voice.md").write_text("   \n", encoding="utf-8")
        voice, warning = load_voice(tmp_path)
        assert voice == DEFAULT_VOICE
        assert warning is not None


class TestTemplate:
    def test_template_loads_from_package_data(self) -> None:
        text = load_template()
        assert "Klyreon ingest prompt" in text
        # All placeholders present so assembly fills every slot.
        slots = (
            "{voice}",
            "{max_body_lines}",
            "{claim_set}",
            "{source_archive_path}",
            "{source_text}",
            "{response_schema}",
        )
        for slot in slots:
            assert slot in text


class TestAssembly:
    def test_everything_reaches_the_prompt(self) -> None:
        prompt = assemble_prompt(
            source_text="BODY-SENTINEL the source body text",
            source_archive_path="sources/archive/2026-05/article-x.md",
            claim_set="CLAIMSET-SENTINEL [{...}]",
            voice="VOICE-SENTINEL be terse",
            max_body_lines=60,
        )
        # Source body reaches the prompt.
        assert "BODY-SENTINEL the source body text" in prompt
        # Voice reaches the prompt.
        assert "VOICE-SENTINEL be terse" in prompt
        # Split rule ceiling reaches the prompt.
        assert "at most **60**" in prompt
        # Claim set reaches the prompt.
        assert "CLAIMSET-SENTINEL" in prompt
        # Archive path reaches the prompt.
        assert "sources/archive/2026-05/article-x.md" in prompt
        # Response schema reaches the prompt (IngestPayload JSON Schema).
        assert '"zettels"' in prompt
        assert '"conflicts"' in prompt
        assert '"corroborations"' in prompt
