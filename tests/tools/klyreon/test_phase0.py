"""Phase 0: closed vocabularies and settings."""

from __future__ import annotations

import pytest
from klyreon.settings import KlyreonSettings
from klyreon.spec.enums import (
    Assent,
    AuxKind,
    ConceptType,
    DoubtMode,
    Lifecycle,
    Relation,
    SourceType,
    ZettelType,
)


class TestEnums:
    """Every enum must match its spec table member-for-member (spec 6-8, 3.3)."""

    def test_source_types(self) -> None:
        assert {t.value for t in SourceType} == {"article", "book", "quote", "transcript"}

    def test_zettel_types(self) -> None:
        assert {t.value for t in ZettelType} == {
            "note",
            "definition",
            "procedure",
            "wiki-article",
            "cheatsheet",
            "snippet",
            "course",
            "ai-prompt",
        }

    def test_concept_types(self) -> None:
        assert {t.value for t in ConceptType} == {
            "thesis",
            "argument",
            "aporia",
            "question",
            "example",
            "observation",
        }

    def test_assent(self) -> None:
        assert {t.value for t in Assent} == {"accepted", "tentative", "rejected", "unknown"}

    def test_lifecycle(self) -> None:
        assert {t.value for t in Lifecycle} == {"fleeting", "literature", "evergreen"}

    def test_doubt_modes(self) -> None:
        assert {t.value for t in DoubtMode} == {
            "disagreement",
            "regress",
            "context-relative",
            "assumption",
            "circular",
        }

    def test_relations_closed_and_capped_at_ten(self) -> None:
        values = {t.value for t in Relation}
        assert values == {
            "supports",
            "contradicts",
            "exemplifies",
            "supersedes",
            "defines",
            "analogous-to",
            "causes",
            "requires",
            "broader-than",
            "narrower-than",
        }
        assert len(values) == 10  # spec 8: capped at ten

    def test_aux_kinds(self) -> None:
        assert {t.value for t in AuxKind} == {"moc", "trail"}


class TestSettings:
    """Defaults match the PRD; env prefix overrides; frozen + extra-forbid."""

    def test_defaults(self) -> None:
        s = KlyreonSettings()
        assert s.backend == "claude"
        assert s.model is None
        assert s.max_sources_per_run == 5
        assert s.source_timeout_seconds == 900
        assert s.max_zettel_body_lines == 60
        assert s.maintenance_window_days == 7
        assert s.pruning_enabled is False
        assert s.prune_window_days == 365
        assert s.git_identity_name == "klyreon"
        assert s.git_identity_email == "klyreon@localhost"

    def test_env_prefix_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_KLYREON_BACKEND", "ollama")
        monkeypatch.setenv("BUVIS_KLYREON_MAX_ZETTEL_BODY_LINES", "42")
        s = KlyreonSettings()
        assert s.backend == "ollama"
        assert s.max_zettel_body_lines == 42

    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValueError, match="extra"):
            KlyreonSettings(nonsense_field=1)  # type: ignore[call-arg]
