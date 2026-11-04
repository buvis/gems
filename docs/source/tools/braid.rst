.. _tool-braid:

braid
=====

Agent skill composer. ``braid`` reads the skill repos listed in
``~/.config/braid/sources.d``, links every skill into the ``~/.agents/skills``
union, and projects that union into Claude Code (``~/.claude/skills``) and,
once enrolled, Kiro (``~/.kiro/skills``). It records what it manages in
``<agents_root>/.braid-state.json`` and only removes links it owns.

Usage
-----

.. code-block:: bash

    braid                               # sync links, backups and state
    braid --dry-run                     # report what a sync would change, write nothing
    braid --check                       # exit 1 when links, resources or state drift
    braid --source ~/git/src/my-skills  # add a source for this run (repeatable)
    braid --policy ./extra.braidignore  # load one more .braidignore (repeatable)
    braid --no-claude                   # skip the Claude projection
    braid --agents-root DIR --claude-root DIR --config-root DIR   # override roots

``--dry-run`` and ``--check`` cannot be combined. A sync prints one line per
change (``LINK[symlink]`` or ``LINK[junction]``, ``BACKUP``, ``REMOVE``); a dry
run prints ``WOULD LINK`` and ``WOULD REMOVE``; a check prints ``MISMATCH``,
``MISMATCH STALE``, ``MISMATCH CHANGED``, ``MISMATCH ORPHAN`` and
``MISMATCH STATE``. Every run ends with a summary:

.. code-block:: text

    braid: 3 linked, 40 current, 2 ignored, 0 removed, 1 backed up, 0 configured, 3 change(s)

A check reports ``drift`` in place of ``change(s)``.

Sources
-------

Each file in ``~/.config/braid/sources.d`` (dot files are skipped) lists one
path per line. Text after ``#`` is a comment and blank lines are ignored. A
leading ``~`` expands to the home directory, and a relative path resolves
against the ``sources.d`` directory.

.. code-block:: text

    # ~/.config/braid/sources.d/repos
    ~/git/src/github.com/buvis/agent-skills
    ../../../git/src/github.com/me/private-skills   # relative to sources.d

A source is a repo root that holds a ``skills/`` directory, or a ``skills/``
directory itself. Each subdirectory with a ``SKILL.md`` is a skill; its name
must match the directory. Two sources that ship the same skill name stop the
run with an error. With no source in ``sources.d`` and no ``--source``, braid
stops and names the ``sources.d`` path to fill.

``.braidignore``
----------------

A ``.braidignore`` file lists skill names to keep out of the Claude
projection, one per line, with ``#`` comments. Ignored skills stay in the
``~/.agents/skills`` union and Kiro still gets them. braid loads every file
that exists from these places:

- ``<agents_root>/.braidignore``
- ``<config_root>/.braidignore``
- each source's repo root (the directory that holds ``skills/``)
- each ``--policy`` file

Kiro
----

Kiro is opt-in. ``--kiro`` enrolls ``~/.kiro`` once; later runs remember the
enrollment from the state file.

.. code-block:: bash

    braid --kiro                        # enroll ~/.kiro and project skills into it
    braid --kiro-root DIR               # enroll another Kiro root
    braid --kiro-agent reviewer         # manage skill resources in <kiro-root>/agents/reviewer.json
    braid --forget-kiro-agent reviewer  # stop managing it; keep its existing resources
    braid --no-kiro                     # skip Kiro this run; keep its links and enrollment

``--kiro-root`` wins over ``BUVIS_BRAID_KIRO_ROOT``, which wins over the saved
enrollment. A non-empty ``BUVIS_BRAID_KIRO_ROOT`` enrolls Kiro on its own, like
``--kiro-root``; an empty one counts as unset. A saved enrollment cannot move to
another root. ``--kiro-agent`` needs an existing agent file and is repeatable, as
is ``--forget-kiro-agent``. ``--no-kiro`` cannot be combined with any other
Kiro option.

Backups
-------

braid never deletes a real file or directory in its way. A sync moves it aside
first, under a per-run ``<stamp>`` directory:

- ``<agents_root>/backups/<stamp>/compose/``
- ``<claude_root>/skills-backup/<stamp>/project/``
- ``<kiro_root>/skills-backup/<stamp>/project/``
- ``<kiro_root>/agent-backup/<stamp>/agents/`` for edited Kiro agent files

Configuration
-------------

Each root has a flag, an env name and a default. The flag wins over the env
name.

============================  ============================  ======================
Flag                          Env name                      Default
============================  ============================  ======================
``--agents-root``             ``BUVIS_BRAID_AGENTS_ROOT``   ``~/.agents``
``--claude-root``             ``BUVIS_BRAID_CLAUDE_ROOT``   ``~/.claude``
``--config-root``             ``BUVIS_BRAID_CONFIG_ROOT``   ``~/.config/braid``
``--kiro-root``               ``BUVIS_BRAID_KIRO_ROOT``     unset (``~/.kiro``)
============================  ============================  ======================

Moving from agent-skills
~~~~~~~~~~~~~~~~~~~~~~~~

braid no longer reads the old ``AGENTS_ROOT``, ``CLAUDE_ROOT``, ``KIRO_ROOT``
and ``AGENT_SKILLS_CONFIG`` env names or ``~/.config/agent-skills``. Move
``sources.d`` to ``~/.config/braid/sources.d`` and rename any env names you
set to the ``BUVIS_BRAID_`` names above.

Exit codes
----------

====  ================================================================
Code  Meaning
====  ================================================================
0     success
1     ``--check`` found drift
2     a rejected option combination, or an error, printed as
      ``braid: <error>`` (bad source, duplicate skill, unreadable state,
      a path braid refuses to replace, a filesystem error)
====  ================================================================
