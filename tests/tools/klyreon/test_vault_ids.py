"""Collision-bumped ID allocation (spec 3.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from klyreon.vault.ids import allocate_id, format_id


class TestAllocateId:
    def test_single_id_is_14_digits_and_agrees_with_created(self, tmp_path: Path) -> None:
        now = dt.datetime(2026, 4, 11, 14, 53, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        allocated = allocate_id(tmp_path, now)
        assert allocated.id == "20260411145300"
        assert len(allocated.id) == 14
        assert format_id(allocated.created) == allocated.id

    def test_ten_ids_in_one_frozen_second_are_consecutive_and_unique(self, tmp_path: Path) -> None:
        now = dt.datetime(2026, 4, 11, 14, 53, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        ids: list[str] = []
        for _ in range(10):
            allocated = allocate_id(tmp_path, now)
            # Simulate the file being written so the next allocation collides.
            (tmp_path / allocated.filename).write_text("x")
            ids.append(allocated.id)
            # created must always agree with the (possibly bumped) id
            assert format_id(allocated.created) == allocated.id

        assert len(set(ids)) == 10, "all ten ids unique"
        expected = [format_id(now + dt.timedelta(seconds=i)) for i in range(10)]
        assert ids == expected, "ids are ten consecutive seconds"
