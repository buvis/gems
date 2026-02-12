from datetime import date, datetime

import pytest

from buvis.pybase.zettel.domain.entities.project.services.log_parser import parse_log


class TestParseLog:
    def test_empty_log(self):
        assert parse_log("") == []
        assert parse_log("   ") == []

    def test_info_entry(self):
        raw = "- [i] 2026-02-10 13:08 - some info text"
        entries = parse_log(raw)
        assert len(entries) == 1
        e = entries[0]
        assert e.status == "info"
        assert e.action is None
        assert e.state is None
        assert e.timestamp == datetime(2026, 2, 10, 13, 8)

    def test_open_entry_with_arrow(self):
        raw = "- [ ] 2026-02-10 13:08 - state text => action text"
        entries = parse_log(raw)
        assert len(entries) == 1
        e = entries[0]
        assert e.status == "open"
        assert e.state == "state text"
        assert e.action == "action text"

    def test_open_entry_without_arrow(self):
        raw = "- [ ] 2026-02-10 13:08 - just action text"
        e = parse_log(raw)[0]
        assert e.status == "open"
        assert e.state is None
        assert e.action == "just action text"

    def test_done_entry(self):
        raw = "- [x] 2026-02-10 13:08 - done thing"
        assert parse_log(raw)[0].status == "done"
        assert parse_log(raw)[0].action == "done thing"

    @pytest.mark.parametrize(
        ("gtd_tag", "expected"),
        [
            ("#gtd/act/now", "now"),
            ("#gtd/act/next", "next"),
            ("#gtd/wait", "wait"),
            ("#gtd/someday", "someday"),
            ("#gtd/act/later", "later"),
            ("#gtd/unknown/tag", "now"),  # unknown defaults to now
        ],
    )
    def test_gtd_list(self, gtd_tag: str, expected: str):
        raw = f"- [ ] 2026-02-10 13:08 - task | {gtd_tag}"
        assert parse_log(raw)[0].gtd_list == expected

    def test_no_gtd_tag(self):
        raw = "- [ ] 2026-02-10 13:08 - task"
        assert parse_log(raw)[0].gtd_list is None

    @pytest.mark.parametrize(
        ("emoji", "expected"),
        [
            ("\u23eb", "highest"),
            ("\U0001f53c", "high"),
            ("\U0001f53d", "low"),
            ("\u23ec", "lowest"),
        ],
    )
    def test_priority(self, emoji: str, expected: str):
        raw = f"- [ ] 2026-02-10 13:08 - task {emoji}"
        assert parse_log(raw)[0].priority == expected

    def test_priority_default_medium(self):
        raw = "- [ ] 2026-02-10 13:08 - task"
        assert parse_log(raw)[0].priority == "medium"

    @pytest.mark.parametrize(
        ("emoji", "attr", "expected"),
        [
            ("\U0001f4c5", "due_date", date(2026, 3, 1)),
            ("\U0001f6eb", "start_date", date(2026, 2, 15)),
            ("\u23f3", "reminder_date", date(2026, 2, 20)),
        ],
    )
    def test_date_field(self, emoji: str, attr: str, expected: date):
        date_str = expected.isoformat()
        raw = f"- [ ] 2026-02-10 13:08 - task {emoji} {date_str}"
        assert getattr(parse_log(raw)[0], attr) == expected

    def test_all_dates(self):
        raw = "- [ ] 2026-02-10 13:08 - task \U0001f4c5 2026-03-01 \U0001f6eb 2026-02-15 \u23f3 2026-02-20"
        e = parse_log(raw)[0]
        assert e.due_date == date(2026, 3, 1)
        assert e.start_date == date(2026, 2, 15)
        assert e.reminder_date == date(2026, 2, 20)

    def test_nested_context(self):
        raw = (
            "- [ ] 2026-02-10 13:08 - task\n"
            "    - context line 1\n"
            "    - context line 2"
        )
        e = parse_log(raw)[0]
        assert e.context == ["- context line 1", "- context line 2"]

    def test_multiple_entries_mixed(self):
        raw = (
            "- [i] 2026-02-10 13:08 - info entry\n"
            "- [ ] 2026-02-11 09:00 - open task => do something | #gtd/act/next \u23eb\n"
            "    - detail 1\n"
            "- [x] 2026-02-12 10:00 - completed task"
        )
        entries = parse_log(raw)
        assert len(entries) == 3
        assert entries[0].status == "info"
        assert entries[1].status == "open"
        assert entries[1].state == "open task"
        assert entries[1].action == "do something"
        assert entries[1].gtd_list == "next"
        assert entries[1].priority == "highest"
        assert entries[1].context == ["- detail 1"]
        assert entries[2].status == "done"

    def test_full_entry_with_all_fields(self):
        raw = "- [ ] 2026-02-10 13:08 - state text => action text | #gtd/act/next \u23eb \U0001f4c5 2026-03-01 \U0001f6eb 2026-02-15 \u23f3 2026-02-20"
        e = parse_log(raw)[0]
        assert e.timestamp == datetime(2026, 2, 10, 13, 8)
        assert e.status == "open"
        assert e.state == "state text"
        assert e.action == "action text"
        assert e.gtd_list == "next"
        assert e.priority == "highest"
        assert e.due_date == date(2026, 3, 1)
        assert e.start_date == date(2026, 2, 15)
        assert e.reminder_date == date(2026, 2, 20)
