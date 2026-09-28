from __future__ import annotations

import json

import pytest
from postup.domain.contracts import (
    SCHEMA_VERSION,
    Commit,
    PortfolioData,
    RepoData,
    SchemaVersionError,
    load_portfolio_data,
    write_outputs,
)


def _repo(owner: str, name: str, *, commits: int = 0) -> RepoData:
    return RepoData(
        path=f"/repos/{name}",
        owner=owner,
        name=name,
        default_branch="main",
        commit_count=commits,
        commits=[Commit(sha=f"abc{i}", date="2026-09-01", author="bob", subject=f"c{i}") for i in range(commits)],
    )


def _data(*repos: RepoData, at: str = "2026-09-28T10:00:00+00:00") -> PortfolioData:
    return PortfolioData(generated_at=at, since_days=60, repos=list(repos))


class TestContractRoundTrip:
    def test_round_trip_preserves_schema_version(self, tmp_path):
        data = _data(_repo("buvis", "gems", commits=2))
        write_outputs(data, tmp_path)

        loaded = load_portfolio_data(tmp_path / "data.json")

        assert loaded.schema_version == SCHEMA_VERSION
        assert loaded.repos[0].name == "gems"
        assert len(loaded.repos[0].commits) == 2
        assert loaded == data

    def test_data_json_carries_schema_version(self, tmp_path):
        write_outputs(_data(_repo("buvis", "gems")), tmp_path)
        raw = json.loads((tmp_path / "data.json").read_text())
        assert raw["schema_version"] == SCHEMA_VERSION


class TestUnknownVersionRejected:
    def test_missing_version_rejected(self, tmp_path):
        target = tmp_path / "data.json"
        target.write_text(json.dumps({"generated_at": "x", "since_days": 60, "repos": []}))
        with pytest.raises(SchemaVersionError):
            load_portfolio_data(target)

    def test_future_version_rejected_loudly(self, tmp_path):
        target = tmp_path / "data.json"
        target.write_text(json.dumps({"schema_version": 999, "generated_at": "x", "since_days": 60, "repos": []}))
        with pytest.raises(SchemaVersionError, match="999"):
            load_portfolio_data(target)


class TestRotation:
    def test_rotation_makes_prev_the_prior_data(self, tmp_path):
        first = _data(_repo("buvis", "gems", commits=1), at="2026-09-27T10:00:00+00:00")
        write_outputs(first, tmp_path)
        assert not (tmp_path / "data-prev.json").exists()  # nothing to rotate on first run

        second = _data(_repo("buvis", "gems", commits=5), at="2026-09-28T10:00:00+00:00")
        write_outputs(second, tmp_path)

        prev = load_portfolio_data(tmp_path / "data-prev.json")
        current = load_portfolio_data(tmp_path / "data.json")
        assert prev.generated_at == first.generated_at
        assert prev.repos[0].commit_count == 1
        assert current.generated_at == second.generated_at
        assert current.repos[0].commit_count == 5


class TestHistoryAppend:
    def test_history_appends_one_line_per_run(self, tmp_path):
        write_outputs(_data(_repo("buvis", "gems", commits=3)), tmp_path)
        write_outputs(_data(_repo("buvis", "gems", commits=4)), tmp_path)

        lines = (tmp_path / "history.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
        rows = [json.loads(line) for line in lines]
        assert rows[0]["repos"]["buvis/gems"]["c"] == 3
        assert rows[1]["repos"]["buvis/gems"]["c"] == 4


class TestDigest:
    def test_digest_lists_commits_per_repo(self, tmp_path):
        write_outputs(_data(_repo("buvis", "gems", commits=2)), tmp_path)
        digest = (tmp_path / "commits-digest.md").read_text()
        assert "## buvis/gems" in digest
        assert "abc0 2026-09-01 c0" in digest

    def test_digest_skips_repos_without_commits(self, tmp_path):
        write_outputs(_data(_repo("buvis", "empty", commits=0)), tmp_path)
        digest = (tmp_path / "commits-digest.md").read_text()
        assert "buvis/empty" not in digest
