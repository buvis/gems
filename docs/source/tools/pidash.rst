.. _tool-pidash:

pidash
======

Read-only TUI dashboard for monitoring autopilot PRD cycle progress.

**Extra:** ``uv tool install buvis-gems[pidash]``

Usage
-----

.. code-block:: bash

    pidash              # watch current directory
    pidash /path/to/project

Watches ``.local/prd-cycle.json`` for state changes written by autopilot and displays
real-time progress through the PRD cycle phases.

Keybindings
-----------

- ``r`` — Refresh (manually reload state file)
- ``q`` — Quit

Display
-------

**Phase pipeline** — shows progress through CATCHUP → PLANNING → WORKING → REVIEWING → DOUBT → DONE
with an animated spinner on the active phase.

**Progress bar** — task completion (e.g. "4/6 completed").

**Tasks panel** — per-task status with markers for pending, in-progress, and completed.
Cycle rework tasks (``[C1]``, ``[C2]``, etc.) are shown with magenta tags.

**Doubts panel** — appears during/after the doubt review phase, showing ``[DOUBT]``
tasks with resolved/total count. Hidden when no doubt tasks exist.

**Decisions panel** — autonomous and deferred decisions color-coded by severity
(critical, high, medium, low).

**Attention banner** — red overlay when autopilot needs a human decision.
