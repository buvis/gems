"""Phase 0: the fixture corpus loads and validates under the 00074 engine."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from klyreon.spec.model import FileKind
from klyreon.spec.parser import parse_file
from klyreon.spec.validator import validate_file, validate_vault

from .conftest import CONFLICT_SOURCES, HAPPY_SOURCES

pytestmark = pytest.mark.klyreon


class TestFixtureSourcesValidate:
    def test_four_happy_sources_validate(self) -> None:
        md = sorted(HAPPY_SOURCES.rglob("*.md"))
        assert len(md) == 4
        for path in md:
            doc = parse_file(path, FileKind.SOURCE)
            errors = validate_file(doc, path=f"sources/2026-05/{path.name}")
            assert not errors, f"{path.name}: {errors}"

    def test_five_conflict_sources_validate(self) -> None:
        md = sorted(CONFLICT_SOURCES.rglob("*.md"))
        assert len(md) == 5
        for path in md:
            doc = parse_file(path, FileKind.SOURCE)
            errors = validate_file(doc, path=f"sources/2026-05/{path.name}")
            assert not errors, f"{path.name}: {errors}"


class TestConflictVaultValidatesClean:
    def test_baseline_vault_is_clean(self, conflict_vault: Path) -> None:
        errors = validate_vault(conflict_vault)
        assert not errors, errors


class TestCannedPayloadsParse:
    def test_happy_markers_cover_four_types(self, payloads: ModuleType) -> None:
        assert set(payloads.HAPPY_PATH) == {
            "article-cache-invalidation",
            "book-thinking-fast-slow-ch1",
            "quote-brooks-no-silver-bullet",
            "transcript-arch-review-2026-05-01",
        }

    def test_conflict_markers_cover_five_cases(self, payloads: ModuleType) -> None:
        assert set(payloads.CONFLICTS) == {
            "conflict-aporia-doubt",
            "conflict-refine",
            "conflict-supersede",
            "conflict-rejected-target",
            "conflict-aporia-zettel",
        }

    def test_all_markers_merge(self, payloads: ModuleType) -> None:
        merged = payloads.all_markers()
        assert len(merged) == len(payloads.HAPPY_PATH) + len(payloads.CONFLICTS) + len(payloads.CORROBORATION)
