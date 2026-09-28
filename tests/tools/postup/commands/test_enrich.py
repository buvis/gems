from __future__ import annotations

import json

from postup.adapters.claude import ClaudeError
from postup.commands.enrich.enrich import CommandEnrich
from postup.domain.contracts import Commit, PortfolioData, RepoData, write_outputs
from postup.settings import PostupSettings


def _seed_collect(out_dir, *shas: str) -> None:
    """Write a valid data.json + commits-digest.md under out_dir."""
    repo = RepoData(
        path="/repos/gems",
        owner="buvis",
        name="gems",
        commits=[Commit(sha=sha, date="2026-09-01", author="bob", subject=f"c {sha}") for sha in shas],
    )
    data = PortfolioData(generated_at="2026-09-28T10:00:00+00:00", since_days=60, repos=[repo])
    write_outputs(data, out_dir)


def _valid_epics_json(sha: str = "abc1234") -> str:
    return json.dumps(
        {
            "summary": "Portfolio moved.",
            "repos": {"buvis/gems": {"epics": [{"title": "X", "summary": "shipped", "shas": [sha]}]}},
            "todos": [
                {
                    "id": "will-be-recomputed",
                    "repo": "buvis/gems",
                    "kind": "judgment",
                    "urgency": "now",
                    "action": "Resume the parked PRD work",
                    "why": "dirty for days",
                },
            ],
        },
    )


class FakeClaude:
    """Injected adapter: scripted responses, availability toggle, call counter."""

    def __init__(self, responses: list, *, available: bool = True) -> None:
        self._responses = list(responses)
        self._available = available
        self.calls = 0
        self.prompts: list[str] = []

    def is_available(self) -> bool:
        return self._available

    def prompt(self, text, *, model=None, timeout=300):
        self.calls += 1
        self.prompts.append(text)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestMissingData:
    def test_missing_data_json_returns_failure(self, tmp_path):
        settings = PostupSettings(out_dir=str(tmp_path / "out"))
        result = CommandEnrich(settings, adapter=FakeClaude([])).execute()
        assert not result.success
        assert "postup collect" in (result.error or "")


class TestClaudeAbsent:
    def test_absent_warns_and_continues_without_file(self, tmp_path):
        out = tmp_path / "out"
        _seed_collect(out, "abc1234")
        result = CommandEnrich(PostupSettings(out_dir=str(out)), adapter=FakeClaude([], available=False)).execute()
        assert result.success  # never blocks the brief
        assert any("claude not found" in w for w in result.warnings)
        assert not (out / "epics.json").exists()


class TestHappyPath:
    def test_valid_response_writes_epics_json_with_info_alert(self, tmp_path):
        out = tmp_path / "out"
        _seed_collect(out, "abc1234")
        fake = FakeClaude([_valid_epics_json()])
        result = CommandEnrich(PostupSettings(out_dir=str(out), model="claude-sonnet"), adapter=fake).execute()

        assert result.success
        assert fake.calls == 1
        assert (out / "epics.json").is_file()
        assert any("will use claude" in i and "claude-sonnet" in i for i in result.info)

        written = json.loads((out / "epics.json").read_text())
        assert written["repos"]["buvis/gems"]["epics"][0]["shas"] == ["abc1234"]
        # Todo id is recomputed deterministically, never trusting the model's.
        assert written["todos"][0]["id"] != "will-be-recomputed"
        assert written["todos"][0]["id"].startswith("buvis/gems:judgment:")

    def test_info_names_cli_default_when_model_unset(self, tmp_path):
        out = tmp_path / "out"
        _seed_collect(out, "abc1234")
        result = CommandEnrich(PostupSettings(out_dir=str(out)), adapter=FakeClaude([_valid_epics_json()])).execute()
        assert any("CLI default" in i for i in result.info)


class TestRetry:
    def test_invalid_then_valid_is_exactly_two_invocations(self, tmp_path):
        out = tmp_path / "out"
        _seed_collect(out, "abc1234")
        fake = FakeClaude(["not json at all", _valid_epics_json()])
        result = CommandEnrich(PostupSettings(out_dir=str(out)), adapter=fake).execute()

        assert result.success
        assert fake.calls == 2  # exactly one retry
        assert (out / "epics.json").is_file()
        # The retry prompt carries the prior errors.
        assert "previous response was rejected" in fake.prompts[1]

    def test_retry_after_claude_error_then_success(self, tmp_path):
        out = tmp_path / "out"
        _seed_collect(out, "abc1234")
        fake = FakeClaude([ClaudeError("timeout"), _valid_epics_json()])
        result = CommandEnrich(PostupSettings(out_dir=str(out)), adapter=fake).execute()
        assert result.success
        assert fake.calls == 2
        assert (out / "epics.json").is_file()


class TestBothInvalid:
    def test_both_invalid_warns_continues_no_partial_file(self, tmp_path):
        out = tmp_path / "out"
        _seed_collect(out, "abc1234")
        fake = FakeClaude(["garbage", "still garbage"])
        result = CommandEnrich(PostupSettings(out_dir=str(out)), adapter=fake).execute()

        assert result.success  # deterministic continue
        assert fake.calls == 2  # first + one retry, no third
        assert not (out / "epics.json").exists()  # no partial file
        assert any("failed after a retry" in w for w in result.warnings)

    def test_hallucinated_sha_both_times_degrades(self, tmp_path):
        out = tmp_path / "out"
        _seed_collect(out, "def5678")  # abc1234 in the response is unknown
        fake = FakeClaude([_valid_epics_json("abc1234"), _valid_epics_json("abc1234")])
        result = CommandEnrich(PostupSettings(out_dir=str(out)), adapter=fake).execute()
        assert result.success
        assert fake.calls == 2
        assert not (out / "epics.json").exists()
