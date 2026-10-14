.. _tool-sysup:

sysup
=====

Configurable, dotfiles-shareable system updater. ``sysup`` runs every updater
that applies to the current host, in order. What runs is defined in
configuration, not code, so adding, removing, or reordering a simple updater is
a config edit rather than a release.

Usage
-----

.. code-block:: bash

    sysup                     # run every applicable updater, in order
    sysup --only brew,helm    # run only these entries (comma list or repeated)
    sysup --tag python        # run only entries carrying this tag
    sysup --list              # print the resolved plan for this host, run nothing
    sysup --dry-run           # show what would run without running it
    sysup status              # read unresolved attention without running updates

Applicability is decided per entry by its ``when`` guard (OS + a binary that
must exist), so there are no platform subcommands: a macOS-only entry simply
carries ``when.os: darwin`` and is skipped on other hosts.

Configuration
-------------

Updaters live in ``buvis-sysup.yaml`` in the buvis config stack
(``$BUVIS_CONFIG_DIR`` → ``~/.config/buvis`` → cwd), deep-merged over a bundled
default. The updater collection is a **flat map keyed by name**, so a machine
layer adds an entry with a new key and overrides a field of an existing entry
by that key — no list-append syntax, and every base key survives unless
explicitly disabled.

.. code-block:: yaml

    # buvis-sysup.yaml
    commands:
      brew:
        order: 10                       # entries run in ascending order
        when: { os: darwin, check: brew }
        steps:                          # run entry: argv arrays, early-abort
          - [brew, update]
          - [brew, upgrade]
          - [brew, cleanup]

      npm-check:
        order: 20
        when: { check: npm-check }
        interactive: true               # inherit stdio instead of capturing
        steps: [[npm-check, -gu]]

      python-packages:
        order: 30
        use: pip-outdated               # use entry: a named built-in capability

      nvim:
        order: 50
        when: { check: nvim }
        use: nvim-mason
        with: { timeout: 600 }          # capability inputs

    prime:                              # session capabilities run first
      - sudo-prime

Per-entry envelope
~~~~~~~~~~~~~~~~~~~

Every entry is exactly one of a ``run`` entry (``steps``: a list of argv arrays,
executed in order with early-abort, no shell) or a ``use`` entry (``use``: a
named built-in capability, with optional ``with`` inputs). Common fields:

============================  ==============================================================
Field                         Meaning
============================  ==============================================================
``order``                     integer; entries run ascending (default 100)
``enabled``                   set ``false`` to disable a merged/bundled entry (default true)
``when.os``                   ``darwin`` / ``linux`` / ``win32``; skipped on a non-match
``when.check``                binary name; skipped (reported) if ``shutil.which`` misses it
``interactive``               inherit stdio instead of capturing (default false)
``timeout``                   seconds; ``null`` = no timeout
``continue_on_error``         if true, a failed step does not abort the entry (default false)
``tags``                      list of strings for ``--tag`` filtering
============================  ==============================================================

Only ``$${VAR}`` / ``${VAR}`` substitution applies to ``steps`` values (from the
config loader); there is no shell, so no other expansion happens. Use
``$${VAR}`` to pass a literal ``${VAR}`` through.

Built-in capabilities
~~~~~~~~~~~~~~~~~~~~~~~

The stateful updaters that config cannot express as plain argv ship as
code-owned capabilities, referenced by name:

============================  ================================================================
Capability                    Behaviour / inputs
============================  ================================================================
``helm-repo-update``          ``helm repo update`` guarded by an empty-repo-list check
``nvim-mason``                headless Mason update probe; input ``timeout`` (default 600)
``pip-outdated``              per-interpreter (mise-managed, else PATH ``python3``) pip upgrade
``sudo-prime``                caches sudo credentials with a background refresher (``prime:``)
============================  ================================================================

An unknown capability name, or an unknown ``with`` input, is a config error
reported clearly on load — never a stack trace.

Sharing across machines
~~~~~~~~~~~~~~~~~~~~~~~~~

The buvis config stack is itself managed by ``dot``. Track ``buvis-sysup.yaml``
(``dot add``) to share your updater set across machines. For a value that must
live on **one** machine only, put it in a sibling ``buvis-sysup.local.yaml`` and
**do not** ``dot add`` it: the loader gives ``*.local.yaml`` a higher priority
than its shared twin, so it overrides per-key while staying untracked.

.. code-block:: yaml

    # buvis-sysup.local.yaml  (machine-local, never `dot add`ed)
    commands:
      helm:
        enabled: false        # this box has no helm repos — skip it here only
      work-vpn:
        order: 5
        steps: [[sudo, work-vpn-refresh]]

Because ``*.local.yaml`` is deliberately untracked, it is not backed up by the
dotfiles repo; keep a separate backup of anything only it holds.

Attention
---------

An ordinary run ends with one summary of everything unresolved, sorted by
command name. Failed, expired and unknown outcomes are red; expiring outcomes
are amber. Each command has one entry containing all of its not-ok messages,
so a later successful step within the same command does not hide an earlier
failure. A complete clean check of that command clears its entry.

Entries persist in ``$XDG_STATE_HOME/sysup/attention.json``, falling back to
``~/.local/state/sysup/attention.json``. The version-one JSON file is written
atomically and records status, details, first-seen and last-checked UTC
timestamps, and whether a notification succeeded. Filtered-out commands retain
their entries, labelled ``not rechecked this run`` in the summary.

``sysup status`` reads this record without loading the updater configuration
or running commands. It prints each entry with its last-checked timestamp, or
``nothing needs attention`` when empty. It exits 1 if any persisted entry is
red, and 0 for an empty or amber-only record.

An ordinary run exits 1 when a result **from that run** is red (previously,
failed steps exited 0). Amber-only results and red entries retained from
earlier runs keep exit 0. ``--list`` and ``--dry-run`` do not even read the
attention record; neither they nor ``sysup status`` write state or push
notifications. Group options go before the subcommand:
``sysup --only brew status`` runs status only and ignores the updater filters;
``sysup status --only brew`` is a usage error.

Configure optional ntfy pushes in the same config stack, including the
machine-local twin:

.. code-block:: yaml

    ntfy:
      url: https://ntfy.example
      topic: sysup
      credentials_file: ~/.config/ntfy/credentials

``NTFY_URL`` and ``NTFY_TOPIC`` independently fill a missing URL or topic.
``credentials_file`` is optional; its path expands ``~`` and its stripped
content is ``user:password`` for Basic authentication. Keep credentials
outside tracked config files.

Each ordinary run sends at most one aggregated message, titled
``sysup on <hostname>: <N> need attention``. Its sorted lines contain status,
name and the first detail. Red entries push on every ordinary run, even if
retained; amber entries push once after appearing and stay quiet after a
successful push (including a red-to-amber transition). A missing endpoint,
unreadable credentials or failed send produces a warning, keeps the entries
pending for retry, and never changes the run's exit code.

Migration from the subcommands
-------------------------------

The former ``sysup mac`` / ``sysup pip`` / ``sysup nvim`` / ``sysup wsl``
subcommands are **removed**. With no user config, plain ``sysup`` reproduces
what ``sysup mac`` did on macOS (brew → npm-check → pip → uv → helm → mise, mise
last) and what ``sysup wsl`` did on Linux (apt → snap), host-selected via
``when``. Replace ``sysup mac`` with ``sysup``; to run a subset use ``--only``
or ``--tag`` (e.g. ``sysup --only brew`` to run just Homebrew).
