.. _tool-braid:

braid
=====

Agent skill composer. ``braid`` reads the skill repos listed under
``sources`` in ``~/.config/buvis/buvis-braid.yaml``, links every skill into the ``~/.agents/skills``
union, and projects that union into Claude Code (``~/.claude/skills``) and,
once enrolled, Kiro (``~/.kiro/skills``). It also composes always-on rules
into Claude Code, Kiro and generated Codex, Copilot, Pi and Gemini instruction
files (see `Rules`_). It records what it manages in
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
    braid --agents-root DIR --claude-root DIR   # override roots

``--dry-run`` and ``--check`` cannot be combined. A sync prints one line per
change (``LINK[symlink]``, ``LINK[junction]`` or ``LINK[hardlink]``,
``GENERATE``, ``BACKUP``, ``REMOVE``); a dry run prints ``WOULD LINK``,
``WOULD GENERATE`` and ``WOULD REMOVE``; a check prints ``MISMATCH``,
``MISMATCH GENERATED``, ``MISMATCH STALE``, ``MISMATCH CHANGED``,
``MISMATCH ORPHAN`` and ``MISMATCH STATE``. Any mode can print
``MISMATCH OVERSIZE`` and ``UNMANAGED``. Every run ends with a summary:

.. code-block:: text

    braid: 3 linked, 1 generated, 40 current, 2 ignored, 0 removed, 1 backed up, 0 configured, 1 unmanaged, 4 change(s)

A check reports ``drift`` in place of ``change(s)``. ``UNMANAGED`` never counts
as drift.

Sources
-------

``sources`` in ``~/.config/buvis/buvis-braid.yaml`` lists one path per entry.
Each entry must be absolute or start with ``~`` (which expands to the home
directory); a relative entry stops the run with an error.

.. code-block:: yaml

    # ~/.config/buvis/buvis-braid.yaml
    sources:
      - ~/git/src/github.com/buvis/agent-skills

A machine-only source goes in ``~/.local/.config/buvis/buvis-braid.yaml`` as
``sources+: [~/work/skills]`` and is appended to the shared list by the
config loader's list directives - no braid code handles the merge.

A source is a repo root that holds any of ``skills/``, ``rules/`` and
``hosts/``, or a ``skills/`` directory itself (which adds skills only). Each
subdirectory of ``skills/`` with a ``SKILL.md`` is a skill; its name
must match the directory. Two sources that ship the same skill name stop the
run with an error. With no source configured and no ``--source``, braid
stops and names ``sources`` in ``~/.config/buvis/buvis-braid.yaml`` to fill.

``.braidignore``
----------------

A ``.braidignore`` file lists skill names to keep out of the Claude
projection, one per line, with ``#`` comments. Ignored skills stay in the
``~/.agents/skills`` union and Kiro still gets them. braid loads every file
that exists from these places:

- ``<agents_root>/.braidignore``
- each source's repo root (the directory that holds ``skills/``)
- each path in ``policies`` in ``buvis-braid.yaml``
- each ``--policy`` file

The same names also drop rules. Unlike skills, an ignored rule leaves every
host projection and every generated file, Kiro included. It stays in the
``~/.agents`` union views.

Rules
-----

Rules are always-on instructions. A source ships them in this layout:

.. code-block:: text

    rules/<name>/RULE.md                 # shared: every host gets it
    hosts/<host>/rules/<name>/RULE.md    # one host only

The known hosts are ``claude``, ``kiro``, ``codex``, ``copilot``, ``pi`` and
``gemini``; any other directory under ``hosts/`` stops the run with an error.
A rule name uses ``a-z``, ``0-9`` and ``-``. Rule names never clash with skill
names. These are errors:

- two sources ship the same shared rule
- a host rule has the same name as a shared rule
- two sources ship the same rule for one host

braid links each rule into a union view, ``~/.agents/rules/<name>`` or
``~/.agents/hosts/<host>/rules/<name>``, then projects the views into each
host:

=======  ========================================  ========================================
Host     Host path                                 Links to
=======  ========================================  ========================================
Claude   ``~/.claude/rules/<name>.md``             the rule's ``RULE.md`` in the view
Kiro     ``<kiro-root>/steering/<name>.md``        the rule's ``RULE.md`` in the view
Codex    ``~/.codex/AGENTS.md``                    ``~/.agents/hosts/codex/AGENTS.md``
Copilot  ``~/.copilot/copilot-instructions.md``    ``~/.agents/hosts/copilot/AGENTS.md``
Pi       ``~/.pi/agent/AGENTS.md``                 ``~/.agents/hosts/pi/AGENTS.md``
Gemini   ``~/.gemini/GEMINI.md``                   ``~/.agents/hosts/gemini/AGENTS.md``
=======  ========================================  ========================================

Claude and Kiro get one file link per rule. Kiro gets rules only once
enrolled, and ``--no-claude`` or ``--no-kiro`` skip that host. Codex, Copilot,
Pi and Gemini read one file, so braid writes a generated file per host at
``~/.agents/hosts/<host>/AGENTS.md`` and links the host path to it. A
``--agents-root`` run still touches these home host paths.

Generated files
~~~~~~~~~~~~~~~

A generated file starts with this header line and a blank line:

.. code-block:: text

    <!-- Generated by braid. Edit the rule sources, not this file. -->

Then come the shared rule bodies, then the host rule bodies, each group in
source order, then by name. braid strips trailing whitespace from each body,
puts one blank line between bodies and ends the file with one newline. A file
over 32768 bytes is still written, but ``MISMATCH OVERSIZE`` reports it as
drift on every run, so ``--check`` keeps failing until you trim the rules.

Unmanaged host files
~~~~~~~~~~~~~~~~~~~~

braid never replaces or backs up a host path it did not create. When
``~/.codex/AGENTS.md`` or another host path is already there, braid reports
``UNMANAGED`` and leaves it. This is not drift. To hand the path to braid,
remove it once; the next sync links it. When a host root such as ``~/.codex``
is missing, braid skips that host without a word. If you remove a host root
after braid recorded its link, the next check shows ``MISMATCH STATE`` once.

Windows
~~~~~~~

When Windows denies a file symlink (winerror 5 or 1314), braid makes a hard
link and prints ``LINK[hardlink]``. A hard link counts as current while it is
the same file as its target. A stale one is backed up and linked again.

Notes
~~~~~

- A rule named ``agents`` clashes with ``AGENTS.md`` in Kiro steering on a
  case-insensitive filesystem: braid backs up ``AGENTS.md``, then replaces it.
- To retire rules, remove the ``rules`` key from ``.braid-state.json`` and the
  links by hand.

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
- ``<claude_root>/rules-backup/<stamp>/project/`` for rule links
- ``<kiro_root>/steering-backup/<stamp>/project/`` for rule links
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
``--kiro-root``               ``BUVIS_BRAID_KIRO_ROOT``     unset (``~/.kiro``)
============================  ============================  ======================

Moving from ~/.config/braid
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

braid warns about but no longer reads ``~/.config/braid`` or
``BUVIS_BRAID_CONFIG_ROOT``; sync still runs. Move the paths from ``sources.d``
into ``sources`` in ``~/.config/buvis/buvis-braid.yaml`` and list your old
``.braidignore`` file under ``policies`` to keep its exclusions active.
Relative ``sources.d`` entries are no longer accepted: convert them to absolute
paths or paths beginning with ``~``. Put machine-only sources and policies in
``~/.local/.config/buvis/buvis-braid.yaml`` using ``sources+:`` and ``policies+:``.
If the old directory contains your policy file, move that file and update
``policies`` first. After migrating, remove the old directory and unset
``BUVIS_BRAID_CONFIG_ROOT``.

Moving from agent-skills
~~~~~~~~~~~~~~~~~~~~~~~~

braid no longer reads the old ``AGENTS_ROOT``, ``CLAUDE_ROOT``, ``KIRO_ROOT``
and ``AGENT_SKILLS_CONFIG`` env names or ``~/.config/agent-skills``. Put the
paths from ``sources.d`` under ``sources`` in
``~/.config/buvis/buvis-braid.yaml`` and rename any env names you set to the
``BUVIS_BRAID_`` names above.

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
