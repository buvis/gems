from __future__ import annotations

import logging
import threading
from pathlib import Path

from textual.message import Message
from textual.worker import get_current_worker

logger = logging.getLogger(__name__)

STATE_FILENAME = "state.json"
STATE_DIR = "dev/local/autopilot"
SESSIONS_DIR = Path.home() / ".pidash" / "sessions"


class StateChanged(Message):
    def __init__(self, raw: str) -> None:
        self.raw = raw
        super().__init__()


class StateFileDeleted(Message):
    pass


class SessionUpdated(Message):
    def __init__(self, session_id: str, raw: str) -> None:
        self.session_id = session_id
        self.raw = raw
        super().__init__()


class SessionRemoved(Message):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__()


def _read_and_post(app: object, state_file: Path) -> None:
    try:
        raw = state_file.read_text(encoding="utf-8")
        app.post_message(StateChanged(raw))  # type: ignore[attr-defined]
    except OSError:
        logger.debug("Failed to read state file", exc_info=True)


def watch_state_file(app: object, project_path: Path, stop_event: threading.Event | None = None) -> None:
    """Thread worker: watches for state.json changes.

    Posts StateChanged or StateFileDeleted messages to the app.
    Must be run via app.run_worker(..., thread=True).

    Always watches the project root with recursive=True so we catch
    .local/ directory creation and subsequent file writes regardless
    of whether .local/ exists at startup.
    """
    from watchfiles import Change, watch

    worker = get_current_worker()
    state_file = project_path / STATE_DIR / STATE_FILENAME

    if stop_event is None:
        stop_event = threading.Event()

    # If state file already exists, read it immediately
    if state_file.is_file():
        _read_and_post(app, state_file)

    # Always watch project root — catches .local/ creation and file writes
    for changes in watch(project_path, stop_event=stop_event, recursive=True, rust_timeout=500):
        if worker.is_cancelled:
            stop_event.set()
            break

        for change_type, changed_path in changes:
            if Path(changed_path) != state_file:
                continue

            if change_type == Change.deleted:
                app.post_message(StateFileDeleted())  # type: ignore[attr-defined]
            elif state_file.is_file():
                _read_and_post(app, state_file)


def _read_and_post_session(app: object, session_file: Path) -> None:
    try:
        raw = session_file.read_text(encoding="utf-8")
        session_id = session_file.stem
        app.post_message(SessionUpdated(session_id, raw))  # type: ignore[attr-defined]
    except OSError:
        logger.debug("Failed to read session file %s", session_file, exc_info=True)


def watch_sessions_dir(app: object, stop_event: threading.Event) -> None:
    """Thread worker: watches ~/.pidash/sessions/ for session file changes.

    Posts SessionUpdated or SessionRemoved messages to the app.
    Must be run via app.run_worker(..., thread=True).
    """
    from watchfiles import Change, watch

    worker = get_current_worker()

    if SESSIONS_DIR.is_dir():
        for f in sorted(SESSIONS_DIR.glob("*.json")):
            _read_and_post_session(app, f)

    # Create dir if missing so watchfiles has something to watch
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    for changes in watch(SESSIONS_DIR, stop_event=stop_event, rust_timeout=500):
        if worker.is_cancelled:
            stop_event.set()
            break

        for change_type, changed_path in changes:
            p = Path(changed_path)
            if p.suffix != ".json":
                continue

            session_id = p.stem
            if change_type == Change.deleted:
                app.post_message(SessionRemoved(session_id))  # type: ignore[attr-defined]
            elif p.is_file():
                _read_and_post_session(app, p)
