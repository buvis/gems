from __future__ import annotations

import pytest
from postup.domain.contracts import Commit, PortfolioData, RepoData
from postup.domain.epics import (
    EPICS_SCHEMA_VERSION,
    EpicsPayload,
    EpicsValidationError,
    stable_todo_id,
    validate_epics,
)


def _data(*shas: str) -> PortfolioData:
    repo = RepoData(
        path="/repos/gems",
        owner="buvis",
        name="gems",
        commits=[Commit(sha=sha, date="2026-09-01", author="bob", subject=f"c {sha}") for sha in shas],
    )
    return PortfolioData(generated_at="2026-09-28T10:00:00+00:00", since_days=60, repos=[repo])


def _valid_raw() -> dict:
    return {
        "summary": "Things moved.",
        "repos": {"buvis/gems": {"epics": [{"title": "feature X", "summary": "shipped X", "shas": ["abc1234"]}]}},
        "todos": [
            {
                "id": "buvis/gems:judgment:resume-work",
                "repo": "buvis/gems",
                "kind": "judgment",
                "urgency": "soon",
                "action": "Resume the parked PRD work",
                "why": "dirty for 11 days",
            },
        ],
    }


class TestValidPayload:
    def test_valid_payload_parses(self):
        payload = validate_epics(_valid_raw(), _data("abc1234"))
        assert isinstance(payload, EpicsPayload)
        assert payload.schema_version == EPICS_SCHEMA_VERSION
        assert payload.repos["buvis/gems"].epics[0].title == "feature X"
        assert payload.todos[0].urgency == "soon"
        assert payload.todos[0].importance == "high"  # default applied
        assert payload.todos[0].effort == "medium"  # default applied


class TestInvalidPayload:
    def test_missing_summary_rejected(self):
        raw = _valid_raw()
        del raw["summary"]
        with pytest.raises(EpicsValidationError):
            validate_epics(raw, _data("abc1234"))

    def test_bad_urgency_rejected(self):
        raw = _valid_raw()
        raw["todos"][0]["urgency"] = "urgent"
        with pytest.raises(EpicsValidationError):
            validate_epics(raw, _data("abc1234"))

    def test_unknown_field_rejected(self):
        raw = _valid_raw()
        raw["unexpected"] = True
        with pytest.raises(EpicsValidationError):
            validate_epics(raw, _data("abc1234"))

    def test_non_object_rejected(self):
        with pytest.raises(EpicsValidationError):
            validate_epics("not a dict", _data("abc1234"))


class TestShaCrossCheck:
    def test_known_sha_accepted(self):
        payload = validate_epics(_valid_raw(), _data("abc1234", "def5678"))
        assert payload.repos["buvis/gems"].epics[0].shas == ["abc1234"]

    def test_unknown_sha_rejected(self):
        with pytest.raises(EpicsValidationError, match="unknown SHA"):
            validate_epics(_valid_raw(), _data("def5678"))  # abc1234 not present

    def test_hallucinated_sha_reason_names_the_sha(self):
        with pytest.raises(EpicsValidationError) as excinfo:
            validate_epics(_valid_raw(), _data("zzz9999"))
        assert any("abc1234" in reason for reason in excinfo.value.reasons)


class TestStableIds:
    def test_same_input_same_id(self):
        first = stable_todo_id("buvis/gems", "Resume the parked PRD work")
        second = stable_todo_id("buvis/gems", "Resume the parked PRD work")
        assert first == second

    def test_different_action_different_id(self):
        base = stable_todo_id("buvis/gems", "Resume the parked PRD work")
        other = stable_todo_id("buvis/gems", "Delete the stale branch")
        assert base != other

    def test_id_shape_is_content_derived(self):
        todo_id = stable_todo_id("buvis/gems", "Resume the parked PRD work")
        assert todo_id.startswith("buvis/gems:judgment:")
        assert "resume-the-parked-prd-work" in todo_id
