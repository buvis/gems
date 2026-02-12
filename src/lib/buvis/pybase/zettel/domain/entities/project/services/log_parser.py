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
    "\U0001f53c": "high",
    "\u23eb": "highest",
}

_DATE_EMOJI_RE = re.compile(
    r"[\U0001f4c5\U0001f6eb\u23f3] \d{4}-\d{2}-\d{2}",
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
    return "medium"


def _parse_date_emoji(text: str, emoji: str) -> date | None:
    pattern = re.compile(re.escape(emoji) + r" (\d{4}-\d{2}-\d{2})")
    m = pattern.search(text)
    if m:
        return date.fromisoformat(m.group(1))
    return None


def _parse_gtd(text: str) -> str | None:
    for tag, name in _GTD_MAP.items():
        if tag in text:
            return name
    m = re.search(r"#gtd/\S+", text)
    if m:
        return "now"
    return None


def _strip_metadata(text: str) -> str:
    """Remove GTD tags, priority emojis, and date emojis from text."""
    result = text
    result = re.sub(r"#gtd/\S+", "", result)
    for emoji in _PRIORITY_MAP:
        result = result.replace(emoji, "")
    result = re.sub(r"[📅🛫⏳] \d{4}-\d{2}-\d{2}", "", result)
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
        gtd_list = _parse_gtd(rest)
        priority = _parse_priority(rest)
        due_date = _parse_date_emoji(rest, "\U0001f4c5")
        start_date = _parse_date_emoji(rest, "\U0001f6eb")
        reminder_date = _parse_date_emoji(rest, "\u23f3")

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
                due_date=due_date,
                start_date=start_date,
                reminder_date=reminder_date,
                context=context,
            ),
        )

    return entries
