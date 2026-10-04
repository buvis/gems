"""Fixture-pair tests for the brief-portfolio parity gate (PRD 00070).

Exercises the parity rule headlessly, without touching the real portfolio:

* a matching skill/postup pair PASSES (naming/shape mapping allowed);
* a postup output MISSING one per-repo signal field FAILS and names the exact
  absent field;
* narrative/epic *content* differences do NOT fail (LLM nondeterminism excluded);
* a missing or schema-invalid ``epics.json`` DOES fail (enrichment structural).

The parity runner lives at ``tools/lib/parity_brief_portfolio.py`` (tracked but not
importable as a package), loaded here via importlib the same way
``tests/dev/test_check_tool_wiring.py`` loads its dev script.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

_script = Path(__file__).resolve().parents[3] / "tools" / "lib" / "parity_brief_portfolio.py"
_spec = importlib.util.spec_from_file_location("parity_brief_portfolio", _script)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["parity_brief_portfolio"] = _mod
_spec.loader.exec_module(_mod)

compare = _mod.compare
render_checklist = _mod.render_checklist


def _skill_repo() -> dict:
    """A skill-collected repo carrying every per-repo signal field."""
    return {
        "owner": "buvis",
        "name": "gems",
        "org": "buvis",
        "path": "/repos/gems",
        "description": "the monorepo",
        "language": "Python",
        "default_branch": "master",
        "stars": 3,
        "visibility": "public",
        "pushed_at": "2026-09-28",
        "commits": [{"sha": "abc123", "date": "2026-09-01", "author": "bob", "subject": "c"}],
        "commit_count": 1,
        "releases": [{"tag": "v1", "name": "v1", "date": "2026-08-01", "prerelease": False}],
        "last_tag": "v1",
        "unreleased_commits": 4,
        "issues": [{"number": 1, "title": "i", "created": "2026-09-01", "labels": []}],
        "prs": [{"number": 2, "title": "p", "author": "bob", "created": "2026-09-02"}],
        "ci": [{"workflow": "ci", "status": "completed", "conclusion": "success", "url": "u", "date": "2026-09-02"}],
        "security": [{"kind": "dependabot", "severity": "high", "title": "x", "url": "u"}],
        "branches": {"stray": [{"name": "wip", "date": "2026-09-01", "merged": False}], "worktrees": ["/wt/x"]},
        "prds": {"backlog": ["00070"], "wip": [{"title": "w", "idle_days": 2}], "done_count": 5},
        "changelog_unreleased": True,
        "brush_last_run": "2026-09-20",
        "purge_last_run": "2026-09-19",
        "local": {
            "branch": "feat/x",
            "dirty": 2,
            "dirty_since_days": 3,
            "ahead": 1,
            "behind": 0,
            "stashes": 1,
        },
        "errors": [],
    }


def _postup_repo() -> dict:
    """A postup-collected repo (PortfolioData shape) covering the same signals."""
    return {
        "path": "/repos/gems",
        "owner": "buvis",
        "name": "gems",
        "default_branch": "master",
        "description": "the monorepo",
        "language": "Python",
        "stars": 3,
        "commit_count": 1,
        "commits": [{"sha": "abc123", "date": "2026-09-01", "author": "bob", "subject": "c"}],
        "releases": [{"tag": "v1", "name": "v1", "date": "2026-08-01", "prerelease": False}],
        "last_tag": "v1",
        "unreleased_commits": 4,
        "issues": [{"number": 1, "title": "i", "created": "2026-09-01", "labels": []}],
        "prs": [{"number": 2, "title": "p", "author": "bob", "created": "2026-09-02"}],
        "ci": [{"workflow": "ci", "status": "completed", "conclusion": "success", "url": "u"}],
        "security": [{"kind": "dependabot", "severity": "high", "title": "x", "url": "u"}],
        "branches": {"stray": [{"name": "wip", "date": "2026-09-01", "merged": False}], "worktrees": ["/wt/x"]},
        "prds": {"backlog": ["00070"], "wip": [{"title": "w", "idle_days": 2}], "done_count": 5},
        "changelog_unreleased": True,
        "brush_last_run": "2026-09-20",
        "local": {
            "branch": "feat/x",
            "dirty": 2,
            "dirty_since_days": 3,
            "ahead": 1,
            "behind": 0,
            "stashes": 1,
        },
        "errors": [],
    }


def _skill_data() -> dict:
    return {
        "generated_at": "2026-09-29T05:00:00+00:00",
        "since_days": 60,
        "repos": [_skill_repo()],
        "skipped": [],
        "external": {"review_requested": [], "authored": [{"repo": "x/y", "number": 9, "title": "t", "url": "u"}]},
    }


def _postup_data(*, epics_present: bool = True) -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-09-29T05:01:00+00:00",
        "since_days": 60,
        "repos": [_postup_repo()],
        "skipped": [],
        "external": {"review_requested": [], "authored": [{"repo": "x/y", "number": 9, "title": "t", "url": "u"}]},
        "epics_present": epics_present,
    }


class TestMatchingPairPasses:
    def test_matching_pair_passes(self):
        result = compare(_skill_data(), _postup_data())
        assert result.passed, result.field_gaps
        assert result.field_gaps == []
        assert result.repos[0].slug == "buvis/gems"
        assert result.repos[0].missing == []

    def test_checklist_renders_pass_verdict(self):
        body = render_checklist(compare(_skill_data(), _postup_data()), repo_set_source="fixture")
        assert "PASS — full coverage" in body
        assert "`buvis/gems`" in body


class TestMissingFieldFails:
    def test_missing_top_level_signal_named(self):
        postup = _postup_data()
        del postup["repos"][0]["security"]
        result = compare(_skill_data(), postup)
        assert not result.passed
        assert "buvis/gems: security" in result.field_gaps

    def test_missing_nested_signal_named(self):
        """A per-repo sub-field (local.stashes) the skill emits and postup omits is a named gap."""
        postup = _postup_data()
        del postup["repos"][0]["local"]["stashes"]
        result = compare(_skill_data(), postup)
        assert not result.passed
        assert "buvis/gems: local.stashes" in result.field_gaps

    def test_checklist_lists_the_gap(self):
        postup = _postup_data()
        del postup["repos"][0]["prds"]
        body = render_checklist(compare(_skill_data(), postup), repo_set_source="fixture")
        assert "FAIL" in body
        assert "buvis/gems: prds" in body


class TestContentDifferencesDoNotFail:
    def test_narrative_and_commit_content_differ_still_passes(self):
        """Different commit subjects / issue titles are content, not coverage — parity holds."""
        skill = _skill_data()
        postup = _postup_data()
        skill["repos"][0]["commits"][0]["subject"] = "totally different wording"
        skill["repos"][0]["issues"][0]["title"] = "renamed issue"
        postup["repos"][0]["description"] = "a differently phrased description"
        result = compare(skill, postup)
        assert result.passed, result.field_gaps


class TestEnrichmentStructural:
    def test_missing_epics_fails(self):
        result = compare(_skill_data(), _postup_data(epics_present=False))
        assert not result.passed
        assert any("<enrichment>" in gap for gap in result.field_gaps)

    def test_schema_invalid_epics_fails(self, tmp_path):
        """A present-but-schema-invalid epics.json is a gap (structural check on disk)."""
        _write_postup_dir(tmp_path, epics_payload={"schema_version": 1})  # missing required 'summary'
        result = compare(_skill_data(), _postup_data(epics_present=False), postup_out_dir=tmp_path)
        assert not result.passed
        assert any("<enrichment>" in gap and "schema-invalid" in gap for gap in result.field_gaps)

    def test_valid_epics_on_disk_covers(self, tmp_path):
        _write_postup_dir(
            tmp_path,
            epics_payload={"schema_version": 1, "summary": "s", "repos": {}, "todos": []},
        )
        result = compare(_skill_data(), _postup_data(epics_present=False), postup_out_dir=tmp_path)
        assert result.enrichment_covered, result.enrichment_note


class TestRepoSetDifferenceIsConfigNote:
    def test_extra_skill_repo_is_not_a_parity_failure(self):
        skill = _skill_data()
        extra = _skill_repo()
        extra["name"] = "cellar"
        extra["path"] = "/repos/cellar"
        skill["repos"].append(extra)
        result = compare(skill, _postup_data())
        assert result.passed, result.field_gaps  # a repo-set difference alone does not fail
        assert "buvis/cellar" in result.skill_only_repos
        body = render_checklist(result, repo_set_source="fixture")
        assert "Config note" in body
        assert "buvis/cellar" in body


def _write_postup_dir(out_dir: Path, *, epics_payload: dict) -> None:
    """Write a minimal valid data.json + the given epics.json into out_dir."""
    data = {
        "schema_version": 1,
        "generated_at": "2026-09-29T05:01:00+00:00",
        "since_days": 60,
        "repos": [],
        "skipped": [],
        "external": {"review_requested": [], "authored": []},
    }
    (out_dir / "data.json").write_text(json.dumps(data), encoding="utf-8")
    (out_dir / "epics.json").write_text(json.dumps(epics_payload), encoding="utf-8")


def test_deepcopy_fixtures_are_independent():
    """Guard: mutating one comparison's input must not leak into another."""
    a = _skill_data()
    b = copy.deepcopy(a)
    a["repos"][0]["security"] = []
    assert b["repos"][0]["security"]
