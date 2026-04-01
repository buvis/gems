from __future__ import annotations

from pathlib import Path

from pidash.tui.watcher import SESSIONS_DIR, SessionRemoved, SessionUpdated


class TestSessionMessages:
    def test_session_updated_carries_fields(self) -> None:
        msg = SessionUpdated("abc123", '{"prd": "test"}')
        assert msg.session_id == "abc123"
        assert msg.raw == '{"prd": "test"}'

    def test_session_removed_carries_session_id(self) -> None:
        msg = SessionRemoved("abc123")
        assert msg.session_id == "abc123"

    def test_sessions_dir_points_to_home(self) -> None:
        assert SESSIONS_DIR == Path.home() / ".pidash" / "sessions"
