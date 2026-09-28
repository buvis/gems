from __future__ import annotations

import json

import pytest
from postup.adapters.gh import GhAdapter, GhError


class _Proc:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _patch(mocker, side_effect):
    return mocker.patch("postup.adapters.gh.subprocess.run", side_effect=side_effect)


class TestMeta:
    def test_meta_parses_fields(self, mocker):
        payload = {
            "default_branch": "main",
            "description": "the gems",
            "language": "Python",
            "stargazers_count": 12,
        }
        _patch(mocker, lambda *a, **k: _Proc(stdout=json.dumps(payload)))
        meta = GhAdapter().meta("buvis", "gems")
        assert meta.default_branch == "main"
        assert meta.stars == 12
        assert meta.language == "Python"

    def test_unauthenticated_raises(self, mocker):
        _patch(mocker, lambda *a, **k: _Proc(stderr="gh: not logged in", returncode=1))
        with pytest.raises(GhError):
            GhAdapter().meta("buvis", "gems")

    def test_missing_binary_raises(self, mocker):
        _patch(mocker, FileNotFoundError("gh"))
        with pytest.raises(GhError):
            GhAdapter().meta("buvis", "gems")


class TestIssuesAndPRs:
    def test_issues_filters_pull_requests(self, mocker):
        items = [
            {"number": 1, "title": "a bug", "created_at": "2026-09-01T00:00:00Z", "labels": [{"name": "bug"}]},
            {"number": 2, "title": "a pr", "pull_request": {}, "created_at": "2026-09-02T00:00:00Z"},
        ]
        _patch(mocker, lambda *a, **k: _Proc(stdout=json.dumps(items)))
        issues = GhAdapter().issues("buvis", "gems")
        assert [i.number for i in issues] == [1]
        assert issues[0].labels == ["bug"]

    def test_prs_fold_checks_state(self, mocker):
        prs = [
            {
                "number": 5,
                "title": "feature",
                "author": {"login": "bob"},
                "isDraft": False,
                "createdAt": "2026-09-10T00:00:00Z",
                "reviewDecision": "APPROVED",
                "labels": [],
                "statusCheckRollup": [{"conclusion": "SUCCESS"}, {"conclusion": "SUCCESS"}],
            },
        ]
        _patch(mocker, lambda *a, **k: _Proc(stdout=json.dumps(prs)))
        result = GhAdapter().prs("buvis", "gems")
        assert result[0].checks == "passing"
        assert result[0].review == "APPROVED"
        assert result[0].author == "bob"

    def test_prs_failing_check(self, mocker):
        prs = [
            {
                "number": 6,
                "title": "wip",
                "author": None,
                "isDraft": True,
                "createdAt": "2026-09-10T00:00:00Z",
                "statusCheckRollup": [{"conclusion": "FAILURE"}],
            },
        ]
        _patch(mocker, lambda *a, **k: _Proc(stdout=json.dumps(prs)))
        result = GhAdapter().prs("buvis", "gems")
        assert result[0].checks == "failing"
        assert result[0].author == "?"


class TestCI:
    def test_ci_latest_per_workflow(self, mocker):
        payload = {
            "workflow_runs": [
                {
                    "name": "Test",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "u1",
                    "created_at": "2026-09-10T00:00:00Z",
                },
                {
                    "name": "Test",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "u0",
                    "created_at": "2026-09-09T00:00:00Z",
                },
            ],
        }
        _patch(mocker, lambda *a, **k: _Proc(stdout=json.dumps(payload)))
        runs = GhAdapter().ci("buvis", "gems", "main")
        assert len(runs) == 1  # only latest per workflow
        assert runs[0].conclusion == "success"

    def test_ci_absent_on_403(self, mocker):
        _patch(mocker, lambda *a, **k: _Proc(stderr="HTTP 403: Actions disabled", returncode=1))
        assert GhAdapter().ci("buvis", "gems", "main") == []


class TestSecurity:
    def test_absent_alerts_on_404(self, mocker):
        _patch(mocker, lambda *a, **k: _Proc(stderr="HTTP 404", returncode=1))
        assert GhAdapter().security("buvis", "gems") == []

    def test_alerts_sorted_by_severity(self, mocker):
        dependabot = [
            {
                "security_vulnerability": {"severity": "low"},
                "security_advisory": {"severity": "low", "summary": "minor"},
                "dependency": {"package": {"name": "leftpad"}},
                "html_url": "u-low",
            },
            {
                "security_vulnerability": {"severity": "critical"},
                "security_advisory": {"severity": "critical", "summary": "rce"},
                "dependency": {"package": {"name": "evil"}},
                "html_url": "u-crit",
            },
        ]

        def side_effect(argv, **_kwargs):
            path = argv[2]
            if "dependabot" in path:
                return _Proc(stdout=json.dumps(dependabot))
            return _Proc(stdout="[]")

        _patch(mocker, side_effect)
        alerts = GhAdapter().security("buvis", "gems")
        assert [a.severity for a in alerts] == ["critical", "low"]


class TestExternal:
    def test_external_excludes_known_portfolio_repos(self, mocker):
        prs = [
            {
                "repository": {"nameWithOwner": "buvis/gems"},
                "number": 1,
                "title": "own",
                "createdAt": "2026-09-01T00:00:00Z",
                "url": "u1",
                "isDraft": False,
            },
            {
                "repository": {"nameWithOwner": "other/lib"},
                "number": 2,
                "title": "review me",
                "createdAt": "2026-09-02T00:00:00Z",
                "url": "u2",
                "isDraft": False,
            },
        ]
        _patch(mocker, lambda *a, **k: _Proc(stdout=json.dumps(prs)))
        result = GhAdapter().external_review_requested({"buvis/gems"})
        assert [p.repo for p in result] == ["other/lib"]
