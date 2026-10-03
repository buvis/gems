"""Phase 0 -- the operator registry and the claude payload content."""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.assets.registry import (
    UnknownOperatorError,
    known_operator_names,
    payload_files,
    resolve_target,
)

pytestmark = pytest.mark.klyreon

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SPEC_RELPATH = "docs/reference/klyreon/zettel-format-specification.md"


class TestResolveTarget:
    def test_claude_defaults_to_home_dotclaude(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert resolve_target("claude") == (tmp_path / ".claude").resolve()

    def test_claude_honours_config_dir_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        custom = tmp_path / "custom-claude"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
        assert resolve_target("claude") == custom.resolve()

    def test_empty_config_dir_falls_back_to_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert resolve_target("claude") == (tmp_path / ".claude").resolve()

    def test_unknown_operator_lists_known(self) -> None:
        with pytest.raises(UnknownOperatorError, match="known operators: claude"):
            resolve_target("emacs")

    def test_known_operator_names(self) -> None:
        assert known_operator_names() == ["claude"]


class TestPayloadFiles:
    def test_claude_payload_has_skill_md(self) -> None:
        files = payload_files("claude")
        assert len(files) == 1
        payload, handle = files[0]
        assert payload.install_relpath == "skills/klyreon/SKILL.md"
        assert handle.is_file()

    def test_unknown_operator_rejected(self) -> None:
        with pytest.raises(UnknownOperatorError):
            payload_files("emacs")


class TestSkillContent:
    def test_frontmatter_shape_and_length(self) -> None:
        _, handle = payload_files("claude")[0]
        text = handle.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        end = text.index("\n---\n", 4)
        fm = text[4:end]
        names = [ln for ln in fm.splitlines() if ln.startswith("name:")]
        descs = [ln for ln in fm.splitlines() if ln.startswith("description:")]
        assert names, "frontmatter must carry a name"
        assert descs, "frontmatter must carry a trigger-led description"
        description = descs[0].split(":", 1)[1].strip()
        assert len(description) < 250, "trigger description must be under 250 chars"
        assert description.lower().startswith("use when"), "description must be trigger-led"

    def test_states_the_loop_does_not_read_it(self) -> None:
        _, handle = payload_files("claude")[0]
        normalized = " ".join(handle.read_text(encoding="utf-8").split()).lower()
        assert "autonomous loop does not read this file" in normalized

    def test_referenced_spec_path_exists(self) -> None:
        _, handle = payload_files("claude")[0]
        text = handle.read_text(encoding="utf-8")
        assert _SPEC_RELPATH in text, "SKILL.md must point at the normative spec path"
        assert (_REPO_ROOT / _SPEC_RELPATH).is_file(), "the referenced spec path must exist in the repo"

    def test_mentions_the_two_species_and_closed_vocab(self) -> None:
        _, handle = payload_files("claude")[0]
        normalized = " ".join(handle.read_text(encoding="utf-8").split()).lower()
        assert "source document" in normalized
        assert "zettel" in normalized
        assert "closed" in normalized
