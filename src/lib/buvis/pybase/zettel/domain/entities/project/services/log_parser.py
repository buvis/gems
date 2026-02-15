from __future__ import annotations

import re
from datetime import date, datetime

from buvis.pybase.zettel.domain.value_objects.log_entry import LogEntry

_ENTRY_RE = re.compile(
    r"^- \[(?P<checkbox>[ix ])\] (?P<datetime>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) - (?P<rest>.+)$",
)

_GTD_MAP: dict[str, str] = {
    "#gtd/act/now": "now",
    "#gtd/act/next": "next",
    "#gtd/wait": "wait",
    "#gtd/someday": "someday",
    "#gtd/act/later": "later",
}

_PRIORITY_MAP: dict[str, str] = {
    "\u23ec": "lowest",
    "\U0001f53d": "low",
    "\U0001f53c": "medium",
    "\u23eb": "high",
    "\U0001f53a": "highest",
}

_RECURRENCE_RE = re.compile(r"\U0001f501 [^\U0001f4c5\U0001f6eb\u23f3\u2705\u274c|#]*")

_DATE_EMOJI_RE = re.compile(
    r"[\U0001f4c5\U0001f6eb\u23f3\u2705\u274c] \d{4}-\d{2}-\d{2}",
)


def _parse_status(checkbox: str) -> str:
    if checkbox == "i":
        return "info"
    if checkbox == "x":
        return "done"
    return "open"


def _parse_priority(text: str) -> str:
    for emoji, level in _PRIORITY_MAP.items():
        if emoji in text:
            return level
    return "normal"


def _parse_recurrence(text: str) -> str | None:
    m = _RECURRENCE_RE.search(text)
    if m:
        return m.group(0).removeprefix("\U0001f501 ").strip()
    return None


def _parse_date_emoji(text: str, emoji: str) -> date | None:
    pattern = re.compile(re.escape(emoji) + r" (\d{4}-\d{2}-\d{2})")
    m = pattern.search(text)
    if m:
        return date.fromisoformat(m.group(1))
    return None


def _parse_gtd(text: str) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    found_tags = [tag for tag in _GTD_MAP if tag in text]
    unknown = [m.group() for m in re.finditer(r"#gtd/\S+", text) if m.group() not in _GTD_MAP]

    all_tags = found_tags + unknown
    if len(all_tags) > 1:
        warnings.append("multi_gtd")

    if unknown:
        warnings.append("unknown_gtd")

    if found_tags:
        return _GTD_MAP[found_tags[0]], warnings
    if unknown:
        return "now", warnings
    return None, warnings


def _strip_metadata(text: str) -> str:
    """Remove GTD tags, priority emojis, and date emojis from text."""
    result = text
    result = re.sub(r"#gtd/\S+", "", result)
    for emoji in _PRIORITY_MAP:
        result = result.replace(emoji, "")
    result = re.sub(r"[📅🛫⏳✅❌] \d{4}-\d{2}-\d{2}", "", result)
    result = _RECURRENCE_RE.sub("", result)
    result = re.sub(r"\|", "", result)
    return result.strip()


def _parse_state_action(rest: str, status: str) -> tuple[str | None, str | None]:
    if status == "info":
        return None, None

    clean = _strip_metadata(rest)

    if "=>" in clean:
        parts = clean.split("=>", 1)
        return parts[0].strip(), parts[1].strip()
    return None, clean


def parse_log(raw: str) -> list[LogEntry]:
    if not raw.strip():
        return []

    entries: list[LogEntry] = []
    lines = raw.split("\n")
    i = 0

    while i < len(lines):
        m = _ENTRY_RE.match(lines[i])
        if not m:
            i += 1
            continue

        checkbox = m.group("checkbox")
        dt = datetime.strptime(m.group("datetime"), "%Y-%m-%d %H:%M")
        rest = m.group("rest")

        status = _parse_status(checkbox)
        state, action = _parse_state_action(rest, status)
        gtd_list, warnings = _parse_gtd(rest)
        priority = _parse_priority(rest)
        recurrence = _parse_recurrence(rest)
        due_date = _parse_date_emoji(rest, "\U0001f4c5")
        start_date = _parse_date_emoji(rest, "\U0001f6eb")
        reminder_date = _parse_date_emoji(rest, "\u23f3")
        completed_date = _parse_date_emoji(rest, "\u2705")
        cancelled_date = _parse_date_emoji(rest, "\u274c")

        if completed_date or cancelled_date:
            gtd_list = "completed"

        if status == "open" and not due_date and not start_date and not reminder_date:
            warnings.append("open_no_dates")
        if status == "done" and not completed_date:
            warnings.append("done_no_completed")

        context: list[str] = []
        i += 1
        while i < len(lines) and lines[i].startswith("    - "):
            context.append(lines[i].strip())
            i += 1

        entries.append(
            LogEntry(
                timestamp=dt,
                status=status,
                state=state,
                action=action,
                gtd_list=gtd_list,
                priority=priority,
                recurrence=recurrence,
                due_date=due_date,
                start_date=start_date,
                reminder_date=reminder_date,
                completed_date=completed_date,
                cancelled_date=cancelled_date,
                context=context,
                warnings=warnings,
            ),
        )

    return entries
