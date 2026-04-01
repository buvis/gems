.. _tool-pidash:

pidash
======

Read-only TUI dashboard for monitoring autopilot PRD cycle progress.

**Extra:** ``uv tool install buvis-gems[pidash]``

Usage
-----

.. code-block:: bash

    pidash                    # multi-session mode (watch all active sessions)
    pidash /path/to/project   # single-project mode (watch one project)
    pidash --cleanup          # remove session files older than 24h

Multi-session mode
~~~~~~~~~~~~~~~~~~

Running ``pidash`` with no arguments watches ``~/.pidash/sessions/`` for session
files written by autopilot hooks. A sidebar lists all active sessions and the
detail pane shows the selected session's state.

Sessions that haven't been updated for 5 minutes are shown as stale (dimmed).
Files older than 24 hours are auto-cleaned on startup.

Single-project mode
~~~~~~~~~~~~~~~~~~~

Running ``pidash /path/to/project`` watches ``dev/local/autopilot/state.json``
in the given directory. This is the original mode, preserved for backward
compatibility.

Keybindings
-----------

- ``q`` - Quit
- ``r`` - Refresh (manually reload state)
- ``Up/Down`` - Switch between sessions (multi-session mode only)

Display
-------

**Phase pipeline** - shows progress through CATCHUP, PLANNING, WORKING,
REVIEWING, DOUBT, DONE with an animated spinner on the active phase.

**Progress bar** - task completion (e.g. "4/6 completed").

**Session sidebar** (multi-session only) - lists all sessions with project name,
phase badge, and attention indicator. Sessions needing attention sort to the top.
Done and stopped sessions are dimmed.

**Tasks panel** - per-task status with markers for pending, in-progress, and
completed. Cycle rework tasks (``[C1]``, ``[C2]``) shown with magenta tags.

**Doubts panel** - appears during/after the doubt review phase, showing
``[DOUBT]`` tasks with resolved/total count. Hidden when no doubt tasks exist.

**Decisions panel** - autonomous and deferred decisions color-coded by severity
(critical, high, medium, low).

**Attention banner** - red overlay when autopilot needs a human decision.
