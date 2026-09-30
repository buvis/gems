"""Tests for :mod:`postup.domain.derive` — the pure Python view-model.

Fixture-parity seam (PRD 00068 / 00065): these fixtures are SELF-OWNED because
00065 (the shared JS/Python derive fixture payloads) is not built yet. They are
the canonical derive inputs 00065 will later adopt; the JS/Python parity test is
DEFERRED until the JS derive exists and is intentionally not present here.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

from postup.domain.contracts import (
    Branches,
    BranchInfo,
    CIRun,
    Commit,
    ExternalPr,
    ExternalPRs,
    Issue,
    LocalState,
    PortfolioData,
    PrdPipeline,
    PullRequest,
    RepoData,
    SecurityAlert,
    WipPrd,
    write_outputs,
)
from postup.domain.derive import load_view_model


def _repo(  # a fixture builder mirrors the wide RepoData contract
    name: str,
    *,
    owner: str = "buvis",
    commit_count: int = 0,
    commits: list[Commit] | None = None,
    prs: list[PullRequest] | None = None,
    issues: list[Issue] | None = None,
    ci: list[CIRun] | None = None,
    security: list[SecurityAlert] | None = None,
    branches: Branches | None = None,
    prds: PrdPipeline | None = None,
    changelog_unreleased: bool | None = None,
    unreleased_commits: int | None = None,
    local: LocalState | None = None,
    purge_last_run: str | None = None,
    errors: list[str] | None = None,
) -> RepoData:
    return RepoData(
        path=f"/repos/{name}",
        owner=owner,
        name=name,
        commit_count=commit_count,
        commits=commits or [],
        prs=prs or [],
        issues=issues or [],
        ci=ci or [],
        security=security or [],
        branches=branches,
        prds=prds,
        changelog_unreleased=changelog_unreleased,
        unreleased_commits=unreleased_commits,
        local=local,
        purge_last_run=purge_last_run,
        errors=errors or [],
    )


def _enriched_portfolio() -> PortfolioData:
    """A rich, deterministic portfolio touching every attention/todo source."""
    gems = _repo(
        "gems",
        commit_count=42,
        commits=[Commit(sha="abc1234", date="2026-09-20", author="bob", subject="feat: x")],
        prs=[
            PullRequest(number=1, title="feat: y", author="bob"),
            PullRequest(number=2, title="wip", author="bob", draft=True),
        ],
        issues=[Issue(number=9, title="bug")],
        ci=[CIRun(workflow="test", status="completed", conclusion="failure", url="u")],
        security=[SecurityAlert(kind="dependabot", severity="high", title="cve", url="u")],
        branches=Branches(
            stray=[
                BranchInfo(name="old", date="2026-01-01", merged=True),
                BranchInfo(name="live", date="2026-09-01", merged=False),
            ],
        ),
        prds=PrdPipeline(backlog=["a"], wip=[WipPrd(title="stalled", idle_days=30)], done_count=3),
        changelog_unreleased=True,
        unreleased_commits=12,
        local=LocalState(branch="master", dirty=4, dirty_since_days=9, ahead=2, behind=0, stashes=1),
    )
    docs = _repo("docs", commit_count=3)
    external = ExternalPRs(
        review_requested=[
            ExternalPr(repo="other/thing", number=77, title="please review", url="u"),
        ],
    )
    return PortfolioData(
        generated_at="2026-09-28T10:00:00+00:00",
        since_days=60,
        repos=[gems, docs],
        external=external,
    )


def _epics_json(sha: str = "abc1234") -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "summary": "Portfolio moved forward this week.",
            "repos": {"buvis/gems": {"epics": [{"title": "X", "summary": "shipped", "shas": [sha]}]}},
            "todos": [
                {
                    "id": "buvis/gems:judgment:resume-abc",
                    "repo": "buvis/gems",
                    "kind": "judgment",
                    "urgency": "now",
                    "action": "Resume the parked PRD",
                    "why": "dirty for days",
                },
            ],
        },
    )


class TestNeedsCollect:
    def test_missing_data_json_yields_needs_collect_state(self, tmp_path):
        vm = load_view_model(tmp_path)
        assert vm.needs_collect is True
        assert vm.enriched is False
        assert vm.attention == ()
        assert vm.repos == ()

    def test_unreadable_data_json_degrades_to_needs_collect(self, tmp_path):
        (tmp_path / "data.json").write_text("{ not json", encoding="utf-8")
        vm = load_view_model(tmp_path)
        assert vm.needs_collect is True


class TestNotEnriched:
    def test_missing_epics_json_yields_deterministic_subset(self, tmp_path):
        write_outputs(_enriched_portfolio(), tmp_path)
        vm = load_view_model(tmp_path)
        assert vm.needs_collect is False
        assert vm.enriched is False
        assert vm.summary == ""
        # No judgment todos without epics.json — only mechanical ones.
        assert all(todo.kind == "mechanical" for todo in vm.todos)
        # Mechanical todos still derived from the signals.
        actions = {(t.repo, t.action) for t in vm.todos}
        assert ("buvis/gems", "fix failing CI") in actions
        assert ("buvis/gems", "cut a release") in actions
        assert ("buvis/gems", "prune merged branches") in actions

    def test_malformed_epics_json_degrades_to_not_enriched(self, tmp_path):
        write_outputs(_enriched_portfolio(), tmp_path)
        (tmp_path / "epics.json").write_text("{ broken", encoding="utf-8")
        vm = load_view_model(tmp_path)
        assert vm.enriched is False
        assert all(todo.kind == "mechanical" for todo in vm.todos)


class TestEnriched:
    def test_epics_json_adds_summary_and_judgment_todos(self, tmp_path):
        write_outputs(_enriched_portfolio(), tmp_path)
        (tmp_path / "epics.json").write_text(_epics_json(), encoding="utf-8")
        vm = load_view_model(tmp_path)
        assert vm.enriched is True
        assert vm.summary == "Portfolio moved forward this week."
        judgment = [t for t in vm.todos if t.kind == "judgment"]
        assert len(judgment) == 1
        assert judgment[0].action == "Resume the parked PRD"
        assert judgment[0].repo == "buvis/gems"


class TestAttentionQueue:
    def test_attention_is_ranked_now_before_soon_before_later(self, tmp_path):
        write_outputs(_enriched_portfolio(), tmp_path)
        vm = load_view_model(tmp_path)
        kinds = {item.kind for item in vm.attention}
        assert {"ci", "security", "review", "dirty", "wip-idle", "external-review"} <= kinds
        ranks = {"now": 0, "soon": 1, "later": 2}
        seq = [ranks[item.urgency] for item in vm.attention]
        assert seq == sorted(seq), "attention queue must be urgency-ranked"

    def test_attention_is_deterministic_across_calls(self, tmp_path):
        write_outputs(_enriched_portfolio(), tmp_path)
        first = load_view_model(tmp_path).attention
        second = load_view_model(tmp_path).attention
        assert first == second


class TestRepoSummary:
    def test_repo_rows_sorted_and_populated(self, tmp_path):
        write_outputs(_enriched_portfolio(), tmp_path)
        vm = load_view_model(tmp_path)
        assert [r.repo for r in vm.repos] == ["buvis/docs", "buvis/gems"]
        gems = next(r for r in vm.repos if r.repo == "buvis/gems")
        assert gems.commits == 42
        assert gems.open_prs == 2
        assert gems.failing_ci == 1
        assert gems.alerts == 1
        assert gems.unreleased == 12
        assert gems.dirty == 4


class TestSinceLast:
    def test_no_prev_yields_has_prev_false(self, tmp_path):
        # First-ever run: only data.json exists, no data-prev.json.
        write_outputs(_enriched_portfolio(), tmp_path)
        vm = load_view_model(tmp_path)
        assert vm.since_last.has_prev is False
        assert vm.since_last.commits == 0

    def test_prev_snapshot_produces_deltas(self, tmp_path):
        # First write establishes data.json; second write rotates it into
        # data-prev.json, so the third view sees a real diff.
        write_outputs(
            PortfolioData(generated_at="t0", since_days=60, repos=[_repo("gems", commit_count=40)]),
            tmp_path,
        )
        write_outputs(
            PortfolioData(
                generated_at="t1",
                since_days=60,
                repos=[_repo("gems", commit_count=42), _repo("new", commit_count=1)],
            ),
            tmp_path,
        )
        vm = load_view_model(tmp_path)
        assert vm.since_last.has_prev is True
        assert vm.since_last.commits == 3  # (42+1) - 40
        assert vm.since_last.new_repos == ("buvis/new",)
        assert vm.since_last.gone_repos == ()


class TestPortfolioErrors:
    def test_external_pr_fetch_error_surfaces(self, tmp_path):
        data = PortfolioData(
            generated_at="t",
            since_days=60,
            repos=[_repo("gems")],
            external=ExternalPRs(error="gh rate limited"),
        )
        write_outputs(data, tmp_path)
        vm = load_view_model(tmp_path)
        assert any("gh rate limited" in e for e in vm.errors)


def _day_ago(days: int) -> str:
    """Return the ISO calendar day ``days`` days before now (UTC)."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


class TestPurgeCadenceNag:
    def _purge_todo(self, tmp_path, purge_last_run):
        portfolio = PortfolioData(
            generated_at="t",
            since_days=60,
            repos=[_repo("solo", purge_last_run=purge_last_run)],
        )
        write_outputs(portfolio, tmp_path)
        vm = load_view_model(tmp_path)
        return next((t for t in vm.todos if t.action == "purge the trash dir"), None)

    def test_never_purged_raises_nag(self, tmp_path):
        todo = self._purge_todo(tmp_path, None)
        assert todo is not None
        assert todo.why == "never purged"
        assert todo.kind == "mechanical"

    def test_past_threshold_raises_nag(self, tmp_path):
        # 30 days ago == _PURGE_CADENCE_DAYS -> overdue, nag raised.
        todo = self._purge_todo(tmp_path, _day_ago(30))
        assert todo is not None
        assert "purged 30d ago" in todo.why

    def test_within_threshold_does_not_raise_nag(self, tmp_path):
        # 29 days ago < _PURGE_CADENCE_DAYS -> within cadence, no nag.
        todo = self._purge_todo(tmp_path, _day_ago(29))
        assert todo is None


class TestImportIsolation:
    def test_derive_imports_neither_textual_nor_click(self):
        # The derive module is the shared, UI-free seam: importing it must not
        # drag in a UI framework. Assert against a clean import of the module.
        for mod in ("textual", "click"):
            sys.modules.pop(mod, None)
        # Re-import derive fresh and confirm it pulled in no UI framework.
        sys.modules.pop("postup.domain.derive", None)
        import postup.domain.derive  # noqa: F401  # import under test

        assert "textual" not in sys.modules, "derive must not import textual"
        assert "click" not in sys.modules, "derive must not import click"
