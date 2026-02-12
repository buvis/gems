from datetime import date, datetime

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
        entries = parse_log(raw)
        e = entries[0]
        assert e.status == "open"
        assert e.state is None
        assert e.action == "just action text"

    def test_done_entry(self):
        raw = "- [x] 2026-02-10 13:08 - done thing"
        entries = parse_log(raw)
        assert entries[0].status == "done"
        assert entries[0].action == "done thing"

    def test_gtd_act_now(self):
        raw = "- [ ] 2026-02-10 13:08 - task | #gtd/act/now"
        assert parse_log(raw)[0].gtd_list == "now"

    def test_gtd_act_next(self):
        raw = "- [ ] 2026-02-10 13:08 - task | #gtd/act/next"
        assert parse_log(raw)[0].gtd_list == "next"

    def test_gtd_wait(self):
        raw = "- [ ] 2026-02-10 13:08 - task | #gtd/wait"
        assert parse_log(raw)[0].gtd_list == "wait"

    def test_gtd_someday(self):
        raw = "- [ ] 2026-02-10 13:08 - task | #gtd/someday"
        assert parse_log(raw)[0].gtd_list == "someday"

    def test_gtd_act_later(self):
        raw = "- [ ] 2026-02-10 13:08 - task | #gtd/act/later"
        assert parse_log(raw)[0].gtd_list == "later"

    def test_gtd_unknown_defaults_to_now(self):
        raw = "- [ ] 2026-02-10 13:08 - task | #gtd/unknown/tag"
        assert parse_log(raw)[0].gtd_list == "now"

    def test_no_gtd_tag(self):
        raw = "- [ ] 2026-02-10 13:08 - task"
        assert parse_log(raw)[0].gtd_list is None

    def test_priority_highest(self):
        raw = "- [ ] 2026-02-10 13:08 - task ⏫"
        assert parse_log(raw)[0].priority == "highest"

    def test_priority_high(self):
        raw = "- [ ] 2026-02-10 13:08 - task 🔼"
        assert parse_log(raw)[0].priority == "high"

    def test_priority_low(self):
        raw = "- [ ] 2026-02-10 13:08 - task 🔽"
        assert parse_log(raw)[0].priority == "low"

    def test_priority_lowest(self):
        raw = "- [ ] 2026-02-10 13:08 - task ⏬"
        assert parse_log(raw)[0].priority == "lowest"

    def test_priority_default_medium(self):
        raw = "- [ ] 2026-02-10 13:08 - task"
        assert parse_log(raw)[0].priority == "medium"

    def test_due_date(self):
        raw = "- [ ] 2026-02-10 13:08 - task 📅 2026-03-01"
        assert parse_log(raw)[0].due_date == date(2026, 3, 1)

    def test_start_date(self):
        raw = "- [ ] 2026-02-10 13:08 - task 🛫 2026-02-15"
        assert parse_log(raw)[0].start_date == date(2026, 2, 15)

    def test_reminder_date(self):
        raw = "- [ ] 2026-02-10 13:08 - task ⏳ 2026-02-20"
        assert parse_log(raw)[0].reminder_date == date(2026, 2, 20)

    def test_all_dates(self):
        raw = "- [ ] 2026-02-10 13:08 - task 📅 2026-03-01 🛫 2026-02-15 ⏳ 2026-02-20"
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
            "- [ ] 2026-02-11 09:00 - open task => do something | #gtd/act/next ⏫\n"
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
        raw = "- [ ] 2026-02-10 13:08 - state text => action text | #gtd/act/next ⏫ 📅 2026-03-01 🛫 2026-02-15 ⏳ 2026-02-20"
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
