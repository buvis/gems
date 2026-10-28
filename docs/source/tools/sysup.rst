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
    sysup refresh gh-agent    # walk through renewing a tracked credential on this terminal

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
``uv-tool-python``            moves every uv tool install to the global mise Python minor with ``uv tool upgrade --python``; no inputs
``sudo-prime``                caches sudo credentials with a background refresher (``prime:``)
``gh-token-expiry``           gh token: expiration header + a private-repo grant probe; inputs ``config_dir``, ``probe``
``x509-expiry``               PEM file or TLS endpoint not-after; one of ``path`` / ``host``; needs the ``cryptography`` extra
============================  ================================================================

An unknown capability name, or an unknown ``with`` input, is a config error
reported clearly on load — never a stack trace.

On macOS, ``uv-tool-python`` runs at order 35, before ``uv`` at order 40.
It runs ``uv tool upgrade --python <minor> <tool>`` for unpinned tools and tools
with an older numeric Python pin, moving them to the global mise Python minor;
equal and newer pins stay unchanged. The upgrade also bumps package versions,
which the next ``uv tool upgrade --all`` would do anyway. The upgrade keeps the
receipt's recorded requirements (an editable checkout, extras, constraints,
index options) and only switches the interpreter, so customized receipts are
moved in place. uv leaves the receipt's ``python`` pin as it was after a move,
so sysup also reads the Python minor of the tool's environment and skips tools
already on the global minor. A failed move makes uv delete the receipt, so sysup
restores it, then attempts an upgrade on the prior minor, or without a pin if
previously unpinned, and reports any restore or rollback failure. Unpinned rollback does not guarantee the original
interpreter. Malformed, missing, or unsupported-selector receipts are visibly
skipped and left untouched. The plan continues, so skipped tools may still fail
during the later ``uv tool upgrade --all``.

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

Priming sudo
-------------

An entry that sets ``sudo: true``, or any of whose steps' argv starts with
``sudo``, needs a cached sudo ticket:

.. code-block:: yaml

    commands:
      brew:
        order: 10
        sudo: true          # at least one cask needs sudo partway through
        interactive: true   # brew resets the ticket, so its prompt must be visible
        steps:
          - [brew, upgrade, --no-ask]

Priming only runs when stdin is a TTY and at least one selected entry needs
sudo; ``--list`` and ``--dry-run`` never prime. Before the first command runs,
``sysup`` prompts for your password to cache a sudo ticket, then refreshes it
in the background every 60 seconds (past sudo's 5-minute timeout) for the rest
of the run, stopping the refresher in a ``finally`` so a ``Ctrl-C`` between
entries cannot leak the background thread. At the prompt:

* press **Ctrl-D** to skip priming — later sudo-needing steps then prompt for
  themselves as before, exactly as if priming were never configured;
* press **Ctrl-C** to abort the whole run.

Homebrew resets the sudo ticket before its first sudo call (``sudo
--reset-timestamp``), so priming does not carry over to ``brew upgrade``: a cask
that needs sudo prompts for the password again. The bundled ``brew`` entry
therefore sets ``interactive: true``, so that prompt shows in the terminal. In
captured mode the spinner hides it and the run appears to hang. On a TTY
Homebrew also asks "Do you want to proceed with the upgrade?", so the entry
passes ``--no-ask``.

A missing ``sudo`` binary or a declined prompt is not an error — it is the
same as skipping priming. Each sudo-needing argv step still only inherits its
own child's stdin when it runs (the ``interactive`` scope is per step, not
shared across the whole run), so priming only ever affects whether that step
is prompted again.

Run logs
--------

Every ordinary run (not ``--list`` or ``--dry-run``) writes one log file
before its first command: ``$XDG_STATE_HOME/sysup/logs``, falling back to
``~/.local/state/sysup/logs``. The filename is the run's UTC start time,
``YYYYMMDDTHHMMSSZ.log``; a same-second collision (two runs starting in the
same second) appends a ``-1``, ``-2``, ... suffix, first available name wins.
Older log files beyond the **newest 10** are deleted at the start of each run.
A captured step's section records its argv, exit code, and stdout/stderr
verbatim; a timed-out step records the timeout instead of an exit code; a
``use:`` capability or an ``interactive`` step records only its status, since
nothing was captured. If the log itself cannot be written — directory
creation, file creation, or a write/flush failure — the run stops with an
error instead of continuing silently (stop-on-log-failure).

``sysup`` prints the log's path after every run that reaches one, clean,
amber or red, e.g. ``full log: ~/.local/state/sysup/logs/20261019T120000Z.log``.

Within a ``run:`` entry's ``steps``, each argv step's captured stdout and
stderr are scanned for lines starting with ``error:`` (case-insensitive,
leading whitespace ignored) — this strict heuristic fires even when the step
exits 0, catching tools that report an error without a nonzero exit. Up to 5
matching lines are printed inline; any beyond that are summarized as
``+N more, see log``. A ``run:`` entry still reports exactly **one final
result** for its whole ``steps`` list, never one per step: a genuine step
failure ends the entry early (unless ``continue_on_error``) with a failed
result; otherwise, if any ``error:`` line was seen anywhere in the entry's
output, the entry reports a single ``warned`` result (amber, like
``expiring`` — it does not fail the run or turn the exit code red); with
neither, the entry reports its usual success.

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

Expiry items
------------

Alongside ``commands:``, an ``expiry:`` map tracks credentials with a hard
expiry. Each item names a code-owned expiry capability, its inputs, a warning
threshold, an optional refresh procedure, and the same ``enabled`` / ``when``
envelope as a command. Items are checked **before any command on every ordinary
run** — before ``prime`` too, so a read-only probe never waits on a sudo
prompt. ``--only`` and ``--tag`` never filter items: a filtered run still probes
every applicable item and folds it into the attention record. Items are not
probed under ``--list`` or ``--dry-run``, and ``sysup status`` only reads the
record.

.. code-block:: yaml

    # buvis-sysup.yaml / buvis-sysup.local.yaml
    expiry:
      gh-agent:
        enabled: true
        use: gh-token-expiry
        with:
          config_dir: ~/.config/gh-agent
          probe: repos/<owner>/<private-repo>   # a gh api path needing private access
        warn_days: 30

An item's ``StepResult`` is ``ok``, ``expiring``, ``expired`` or ``unknown``.
``expiring`` is amber (within ``warn_days`` of expiry; exactly ``warn_days`` days
left is already amber); ``expired`` and ``unknown`` are red. A clean ``ok`` check
clears the item's entry; any other outcome records or updates it.

A command may declare ``needs: [item]``. While a needed item is ``expired`` or
``unknown`` **this run**, the command is skipped with a failed step reading
``<command> skipped: <item> is <status>; run: sysup refresh <item>``. ``ok`` and
``expiring`` items never block, and an item that was not checked this run
(disabled, or a ``when`` mismatch) never blocks either.

The bundled ``gh-agent`` item ships **disabled** with no probe, so tracking stays
off until you opt in. Enable it on one host from the untracked
``buvis-sysup.local.yaml`` by supplying a private-repository ``probe`` and
``enabled: true``; the bundled ``config_dir`` and refresh procedure merge in:

.. code-block:: yaml

    # buvis-sysup.local.yaml  (machine-local, never `dot add`ed)
    expiry:
      gh-agent:
        enabled: true
        with:
          probe: repos/myorg/myprivate

``gh-token-expiry`` reads the ``Github-Authentication-Token-Expiration`` header
from ``gh api -i user`` and then probes the grant with one authenticated call
that needs private-repository access, so a token that authenticates but has lost
its repository access reads ``unknown`` rather than ``ok``. Both calls target
**github.com** credentials in the configured directory: the five ambient gh
token/host variables (``GH_TOKEN``, ``GITHUB_TOKEN``, ``GH_ENTERPRISE_TOKEN``,
``GITHUB_ENTERPRISE_TOKEN``, ``GH_HOST``) are stripped from the child
environment and ``--hostname github.com`` is pinned, without ever mutating your
shell's environment.

``x509-expiry`` reads the not-after date of a local PEM ``path`` or of the
certificate a TLS ``host`` (``name`` or ``name:port``, port 443 by default)
presents. It needs the optional ``cryptography`` extra
(``uv tool install 'buvis-gems[sysup-cert]'``); a core-only install reports
``unknown`` with that install hint and keeps tracking gh tokens in the same run.

``sysup refresh <item>`` walks you through renewal on a terminal and re-checks:

* it refuses with ``sysup refresh needs a terminal`` (exit 1) when stdin is not
  a TTY, and runs nothing;
* it prints the item's instructions, waits for Enter, then runs the refresh
  procedure's commands in order, stopping at the first failure;
* a command declaring ``stdin: secret`` receives the pasted secret **only** on
  its standard input — never on argv, in the environment, in logs, in state or
  in a notification — and the secret is dropped immediately after the call; a
  ``gh auth login`` step strips the same five ambient overrides and pins
  github.com;
* after the procedure succeeds the item is re-checked. Only an ``ok`` recheck
  clears the entry; ``expiring`` keeps the amber entry (exit 0), while
  ``expired`` and ``unknown`` keep the entry and exit 1. A refresh never sends a
  notification — you are at the terminal watching the result.

Migration from the subcommands
-------------------------------

The former ``sysup mac`` / ``sysup pip`` / ``sysup nvim`` / ``sysup wsl``
subcommands are **removed**. With no user config, plain ``sysup`` reproduces
what ``sysup mac`` did on macOS (brew → npm-check → pip → uv → helm → mise, mise
last) and what ``sysup wsl`` did on Linux (apt → snap), host-selected via
``when``. Replace ``sysup mac`` with ``sysup``; to run a subset use ``--only``
or ``--tag`` (e.g. ``sysup --only brew`` to run just Homebrew).
