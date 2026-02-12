from datetime import datetime

from buvis.pybase.zettel.domain.entities.project.services.migration.upgrades.migrate_loop_log import (
    extract_log_entries,
    format_log_entries,
)


def test_extract_log_entries():
    content = """
    01.01.2024 12:00 - Entry without action
    02.01.2024 13:00 - Entry with action => Completed
    03.01.2024 14:00 - Another entry without action
    """
    expected_dates = [
        datetime(2024, 1, 1, 12, 0).astimezone(),
        datetime(2024, 1, 2, 13, 0).astimezone(),
        datetime(2024, 1, 3, 14, 0).astimezone(),
    ]
    expected_texts = [
        "Entry without action",
        "Entry with action",
        "Another entry without action",
    ]
    expected_actions = ["", "Completed", ""]

    log_entries, unmatched_lines = extract_log_entries(content)

    assert len(log_entries) == 3
    assert unmatched_lines == []
    for i, (date, text, action) in enumerate(log_entries):
        assert date == expected_dates[i]
        assert text == expected_texts[i]
        assert action == expected_actions[i]


def test_format_log_entries():
    log_entries = [
        (datetime(2024, 1, 1, 12, 0), "Entry without action", ""),
        (datetime(2024, 1, 2, 13, 0), "Entry with action", "something to do"),
    ]
    expected_output = (
        "- [i] 2024-01-01 12:00 - Entry without action\n"
        "- [ ] 2024-01-02 13:00 - Entry with action => something to do | #gtd/act/now 🔼\n"
    )

    result = format_log_entries(log_entries)
    assert result == expected_output


def test_format_log_entries_empty():
    log_entries = []
    expected_output = ""

    result = format_log_entries(log_entries)
    assert result == expected_output
