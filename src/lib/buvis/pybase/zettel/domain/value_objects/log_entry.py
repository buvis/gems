from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class LogEntry:
    timestamp: datetime
    status: str  # "info" | "open" | "done"
    state: str | None
    action: str | None
    gtd_list: str | None
    priority: str  # "lowest" | "low" | "medium" | "high" | "highest"
    due_date: date | None = None
    start_date: date | None = None
    reminder_date: date | None = None
    completed_date: date | None = None
    cancelled_date: date | None = None
    context: list[str] = field(default_factory=list)
