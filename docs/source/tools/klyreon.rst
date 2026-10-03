.. _tool-klyreon:

klyreon
=======

Autonomous Memex-Zettelkasten. ``klyreon`` is the gem that reads, writes, and
validates the Klyreon vault format (the normative format spec lives at
``docs/reference/klyreon/zettel-format-specification.md``), finds and creates
the vault, and commits machine writes under a dedicated identity so authorship
stays detectable. It runs on the core install — no extra.

This first release (PRD 00074) shipped the spec engine, the vault contract, the
git layer, and five commands. Ingest (PRD 00075), operator assets (PRD 00076),
and the autonomous maintain loop plus the scheduler (PRD 00077) complete the
chain — a source dropped into ``sources/`` becomes committed, cross-linked,
promoted knowledge with no human in the path.

The vault root
--------------

Every path inside a zettel or source document is relative to a **root**. klyreon
resolves the root as:

1. ``$KLYREON_ROOT`` (wins outright — used for test isolation), else
2. the ``root`` key in ``$XDG_CONFIG_HOME/klyreon/config.yaml`` (falling back to
   ``~/.config/klyreon/config.yaml``).

A relative root, a missing root directory, or a missing config file fails loudly
and creates nothing. Paths containing ``..`` or escaping the root are rejected.

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Setting
     - Default
     - Description
   * - ``backend``
     - ``claude``
     - LLM backend for later autonomous PRDs.
   * - ``model``
     - (unset)
     - Optional model override.
   * - ``max_sources_per_run``
     - ``5``
     - Ingest cap (PRD B).
   * - ``source_timeout_seconds``
     - ``900``
     - Per-source ingest timeout (PRD B).
   * - ``max_zettel_body_lines``
     - ``60``
     - Oversized-body lint threshold.
   * - ``maintenance_window_days``
     - ``7``
     - Staleness window for the maintenance warning.
   * - ``pruning_enabled``
     - ``false``
     - Whether pruning deletes (PRD D).
   * - ``prune_window_days``
     - ``365``
     - Prune candidate window (PRD D).
   * - ``git_identity_name``
     - ``klyreon``
     - Author name on machine commits.
   * - ``git_identity_email``
     - ``klyreon@localhost``
     - Author email on machine commits.

Settings layer CLI > env (``BUVIS_KLYREON_*``) > YAML config > defaults. The
vault root is **not** a setting — it lives in klyreon's own config file so every
tool finds the vault the same way.

Commands
--------

.. code-block:: bash

    klyreon init [PATH]                      # create the vault skeleton + config
    klyreon init . --force                   # repoint an existing config here
    klyreon new --title "A thesis" --type note --concept-type thesis
    klyreon new --title "ripgrep tip" --type snippet
    klyreon validate                         # exit 1 on any error, 0 when clean
    klyreon validate --json                  # machine-readable report (stdout)
    klyreon export-claims                     # claim index JSON to stdout
    klyreon export-claims --out ~/claims.json # refused if under the vault root
    klyreon status                           # vault dashboard, computed on demand

- ``init`` is idempotent and never runs ``git init``; it warns when the root is
  not a git work tree.
- ``new`` allocates a collision-free 14-digit id; a concept zettel gets
  ``assent: tentative``, ``lifecycle: fleeting``, ``processed: false`` and a
  starter claim; a utility zettel gets none of those.
- ``validate`` runs every mechanical check (file-level + graph-level, including
  the transitive-relation cycle check).
- ``export-claims`` includes claims on ``assent: rejected`` zettels, labelled.
- ``status`` warns when maintenance is stale (every command does), and warns once
  when any installed operator asset pack is behind the running CLI.

Operator assets
---------------

An **operator** is a tool you drive the vault through (today: ``claude``, i.e.
an interactive Claude Code session). Each operator reads from its own home
directory, so klyreon ships an **asset pack** — the knowledge an interactive
session needs to not write files klyreon rejects — and installs it there. The
pack points at ``docs/reference/klyreon/zettel-format-specification.md`` as the
normative format reference rather than restating it.

klyreon's own autonomous loop never reads an installed asset pack: the loop's
prompts ship inside the package. Assets exist only for the human-driven,
interactive side of the same operator.

What is installed, and where:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Operator
     - Install root
   * - ``claude``
     - ``$CLAUDE_CONFIG_DIR`` if set, else ``~/.claude`` — the pack lands at
       ``<root>/skills/klyreon/SKILL.md``.

Everything klyreon installs outside the vault is tracked in a manifest at
``$XDG_STATE_HOME/klyreon/manifest.json`` (each entry records the operator,
absolute path, content hash, and the klyreon version that wrote it). The
manifest is written atomically; an unknown ``schema_version`` is rejected loudly
rather than guessed at, and a missing manifest simply means nothing is installed.

.. code-block:: bash

    klyreon assets install --operator claude   # install (or refresh) the claude pack
    klyreon assets install                     # refresh every operator already installed
    klyreon assets status                      # per file: operator, path, version, drift
    klyreon assets refresh                     # re-install every operator in the manifest
    klyreon assets uninstall --operator claude # remove klyreon's files; keep edited ones

- **install** is re-runnable and never touches the vault, so it works before
  ``init`` and after. A file whose content you have edited since klyreon wrote it
  (or a pre-existing file klyreon did not install) is copied to
  ``<file>.klyreon-backup-YYYYMMDDHHmmSS`` before the shipped version is written,
  and the displaced path is reported. An unchanged, current file is left alone.
- **status** flags a file whose hash drifted (a refresh will back it up) and one
  whose recorded version is behind the running CLI.
- **uninstall** removes a file whose hash still matches the manifest, keeps a
  file you edited (and says so — a human edit is never reverted by automation),
  drops the manifest entries either way, and removes only directories it emptied.

``klyreon init`` offers the install as part of setup: pass ``--operator claude``
(repeatable) to install without prompting, ``--no-input`` to skip the offer, or
answer the per-operator prompt on an interactive terminal. With no TTY the offer
is skipped and the ``klyreon assets install`` command is printed for later.

Backup files accumulate in the operator's directory as the deliberate price of
never destroying an edit; ``assets status`` names every file it would displace so
you can clear old backups yourself.


Maintenance
-----------

``klyreon maintain`` is the autonomous, cron-safe sweep over the whole vault. It
is **deterministic — it makes no LLM call** — so it runs in a vault with no
operator CLI installed and costs nothing per run. It refuses in a non-git vault
(the autonomy gate), takes the single-instance lock, and runs in a fixed order:

1. **Lint** — every mechanical check (the same ones ``validate`` runs),
   reported in the trail and **never auto-fixed**. The fixes are semantic and
   belong to a human or to ingest; lint findings do not block the transitions
   below, but any lint *error* makes the command exit 1.
2. **Lifecycle promotion** — ``fleeting`` → ``literature`` once a zettel cites a
   source and carries a link in either direction; ``literature`` → ``evergreen``
   once two distinct source documents back it (counted across its own
   ``sources`` plus the ``sources`` of every zettel that ``supports`` it). One
   step per sweep; a promotion never resets ``processed``.
3. **Assent transitions** — ``tentative`` → ``accepted`` once two or more
   distinct source documents **other than its own** corroborate it. An open
   ``disagreement`` doubt on the zettel, or one anywhere naming it as a
   ``target``, holds it. ``maintain`` never writes ``rejected``.
4. **MOC membership sync** — each MOC's ``<!-- klyreon:members -->`` block is
   reconciled to the zettels that actually anchor to it: a new anchor is added,
   a dropped or deleted member is removed. Only the marked block is rewritten,
   so human prose around it survives. A MOC named by a zettel but absent from
   disk is a lint finding, not a create — ``maintain`` never authors MOCs.
5. **Prune detection** — see below.

Each transition is its own scoped commit, so an interrupted sweep leaves every
applied zettel committed and the re-run finishes the rest, always ``validate``-
clean. The run writes one ``kind: trail``, ``run: maintain`` journal and stamps
``last_maintain`` into state (which drives the staleness warning every command
emits).

.. code-block:: bash

    klyreon maintain            # run the sweep; exit 1 if lint found errors
    klyreon maintain --dry-run  # report every transition and candidate; write NOTHING

Running ``maintain`` twice in a row makes no change on the second pass (every
rule is a function of vault state).

Pruning
-------

Pruning is overload control, **off until you ask for it**. A prune candidate is
a ``lifecycle: fleeting`` zettel with no inbound and no outbound links, no
corroboration, ``assent`` other than ``rejected``, an empty ``delivered-as``,
and an ``updated`` (or ``created``) older than ``prune_window_days`` (default
365). The two exemptions are deliberate: a ``rejected`` zettel is the record of
what was considered and refused, and a ``delivered-as`` zettel backs work that
already shipped.

Detection **always runs**: the candidate count appears in ``klyreon status`` on
every check, so the backlog stays loud rather than silently growing. Deletion
happens only when ``pruning_enabled: true``. With it on, each candidate is
deleted together with every inbound ``links`` entry, every ``doubts[].target``
naming it, and its MOC membership — all in **one commit**, so no run ever leaves
a dangling reference. git history is the archive, which is why the non-git
refusal matters most here. ``--dry-run`` reports the same list either way.

Scheduler
---------

There is no daemon; the schedule is the external trigger. ``klyreon schedule``
writes, inspects, and removes the platform scheduler artifact and records it in
the manifest (``kind: schedule``).

.. code-block:: bash

    klyreon schedule install              # write the platform artifact (daily 03:00)
    klyreon schedule install --at 05:30   # at a specific time
    klyreon schedule status               # present / loaded / hash-matched + last run
    klyreon schedule uninstall            # remove the artifact and the manifest entry

- On **macOS** it writes ``~/Library/LaunchAgents/net.buvis.klyreon.plist`` with
  label ``net.buvis.klyreon`` and bootstraps it with
  ``launchctl bootstrap gui/<uid>``.
- On **Linux** it writes one crontab line marked ``# klyreon-managed``.
- An unsupported platform (e.g. Windows) fails with the manual equivalent named,
  writing nothing.

The scheduled command is ``/bin/sh -c '<klyreon> ingest; <klyreon> maintain'`` —
a **semicolon, not** ``&&``, so a failed source never stops the maintenance
pass. Both artifacts carry an explicit ``PATH`` captured at install time,
because neither cron nor launchd inherits a login shell's ``PATH``; this is the
trap that silently breaks scheduled runs. Install is **re-runnable** — it boots
out its own label (or strips its own marked crontab lines) before writing, so a
reinstalled binary or a changed time is one re-run — and it never touches the
vault, so it works before ``init``.

``schedule status`` reports the loaded state (``launchctl list`` / ``crontab
-l``) rather than assuming install worked, and a **hash mismatch** means you
edited the artifact: status says so instead of silently rewriting it. A missing
artifact with a live manifest entry is reported, not treated as an error.

``klyreon init`` offers the schedule as part of setup: pass ``--schedule`` to
install without prompting (with ``--at HH:MM`` for the time), answer the prompt
on an interactive terminal, or — with ``--no-input`` or no TTY — have the offer
skipped and the ``klyreon schedule install`` command printed for later. No
autonomous run ever reaches that interactive path.

.. note::

   Discovery's literal criterion 4 — a live cron run of at least seven days on
   the real vault — is a **post-merge soak you run after** ``schedule install``,
   not a CI gate. CI exercises the whole loop against a fixture corpus with the
   stub backend.
