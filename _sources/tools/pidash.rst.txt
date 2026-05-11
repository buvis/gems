.. _tool-pidash:

pidash
======

Read-only TUI dashboard for monitoring autopilot PRD cycle progress.

**Extra:** ``uv tool install buvis-gems[pidash]``

Usage
-----

.. code-block:: bash

    pidash                              # multi-session mode (watch all active sessions)
    pidash --project-path /repo         # single-project mode
    pidash tui /repo                    # equivalent explicit subcommand form
    pidash --cleanup                    # remove session files older than 24h
    pidash hooks install                # register pidash hooks in ~/.claude/settings.json
    pidash hooks status                 # report which hooks are registered
    pidash hooks uninstall              # remove pidash-owned entries from settings.json

Multi-session mode
~~~~~~~~~~~~~~~~~~

Running ``pidash`` with no arguments watches ``~/.pidash/sessions/`` for session
files written by autopilot hooks. A sidebar lists all active sessions and the
detail pane shows the selected session's state.

Sessions that haven't been updated for 5 minutes are shown as stale (dimmed).
Files older than 24 hours are auto-cleaned on startup.

Single-project mode
~~~~~~~~~~~~~~~~~~~

Use ``pidash --project-path /path/to/project`` (or the explicit ``pidash tui
/path/to/project`` subcommand form) to watch ``dev/local/autopilot/state.json``
in the given directory. The earlier bare-positional form ``pidash <path>`` is
no longer accepted: ``pidash`` is now a Click group, so the first non-option
argument is parsed as a subcommand name.

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

Claude Code hooks
-----------------

pidash watches ``~/.pidash/sessions/`` for session files written by a small set
of Claude Code hooks. These hooks ship inside the pidash package; you register
them with one command:

.. code-block:: bash

    pidash hooks install

This writes (or rewrites) six entries in ``~/.claude/settings.json``:

==============  ==================  ==================
Event           Matcher             pidash command
==============  ==================  ==================
Notification    permission_prompt   ``set-attention``
Notification    idle_prompt         ``set-attention``
PostToolUse     TaskUpdate          ``update-tasks``
PostToolUse     Agent               ``sync-agent-return``
PostToolUse     *(default)*         ``clear-attention``
Stop            *(default)*         ``cleanup-session``
==============  ==================  ==================

Unrelated hook entries (e.g. ``notify.py``) are preserved in place. Re-running
``pidash hooks install`` is idempotent and detects legacy
``python3 ~/.claude/hooks/<name>.py`` entries left over from earlier dotfiles
installs, replacing them with ``pidash hooks run <event>`` entries.

``pidash hooks status`` reports which of the six entries are currently
registered and exits non-zero if any are missing. ``pidash hooks uninstall``
removes pidash-owned entries (commands starting with the ``pidash hooks run``
prefix) and leaves everything else untouched.

The ``pidash`` binary must be on the PATH that Claude Code uses to spawn hook
commands. Installing with ``uv tool install buvis-gems[pidash]`` or
``pipx install buvis-gems`` is the common case; a project-local
``uv sync --all-extras`` works too, provided that environment is the active
shell PATH when Claude Code runs.
