.. _tool-postup:

postup
======

**PO**\ rtfolio **ST**\ and\ **UP** — a portfolio standup gem. ``postup`` gathers
the state of every repository in your portfolio into typed, versioned file
contracts that the other postup interfaces consume. It runs fully without any
LLM.

This page documents PRD A: the gem scaffold and the deterministic collector.
Enrichment, the web UI, the TUI, and the text brief land in later PRDs.

Usage
-----

.. code-block:: bash

    postup collect               # collect every configured repo, fetch first
    postup collect --no-fetch    # skip 'git fetch' (fast path, offline-ish)
    postup collect --days 30     # narrow the commit window (default 60)

``postup collect`` discovers repositories, gathers their signals in parallel,
and writes four file contracts under the output directory. A repository whose
data cannot be gathered (``gh`` unauthenticated, a network hiccup, an odd repo
state) degrades into that repository's ``errors`` list and a console warning —
the run never crashes and always exits successfully as long as at least one
repository was discovered.

Configuration
-------------

Settings load from the buvis config stack, ``BUVIS_POSTUP_`` environment
variables, and CLI flags (CLI > env > YAML > defaults).

.. code-block:: yaml

    # postup.yaml (in the buvis config stack, or passed via --config)
    roots:
      - ~/git/src                 # directories scanned for .git repositories
    excludes:
      - ~/git/src/github.com/me/scratch   # repository paths to skip
    out_dir: ~/.local/share/postup        # where the contracts are written
    model: null                           # optional Claude model (later PRD)

============  ==================================================================
Setting       Meaning
============  ==================================================================
``roots``     Directories scanned recursively for ``.git`` repositories. A
              directory holding ``.git`` is a repository and the scan stops
              descending into it.
``excludes``  Absolute repository paths dropped from the discovered set.
``out_dir``   Output directory for the file contracts. Defaults to the XDG data
              dir ``~/.local/share/postup``.
``model``     Optional Claude model name, carried for the enrichment PRD.
============  ==================================================================

Repository discovery uses these roots directly — there is no dependency on
``gita`` or any external registry.

File contracts
--------------

All four files are written atomically (``tempfile`` + ``fsync`` +
``os.replace``) under ``out_dir``:

============================  ====================================================
File                          Contents
============================  ====================================================
``data.json``                 The full portfolio snapshot. Carries a
                              ``schema_version``; an unknown version is rejected
                              loudly on read.
``commits-digest.md``         Per-repository commit digest for later enrichment.
``data-prev.json``            The previous ``data.json``, rotated **before** the
                              new one is written, so it always holds the prior
                              run — it feeds the since-last diff.
``history.jsonl``             One appended summary line per run, feeding the
                              trend view.
============================  ====================================================

Per-repository signals
----------------------

For each repository ``postup collect`` gathers commits, releases / last tag /
unreleased-commit count, open issues and pull requests, CI runs, security
alerts, stray branches and worktrees, the PRD pipeline counts under
``dev/local/prds``, the CHANGELOG ``[Unreleased]`` state, brush-hygiene
recency, local working-tree state (branch / dirty / ahead-behind / stashes),
and portfolio-external PRs (review-requested and authored) via an authenticated
``gh`` CLI plus local ``git``.

Requirements
------------

- ``git`` on ``PATH``.
- An authenticated ``gh`` CLI for forge data. Its absence degrades per
  repository into ``errors`` rather than failing the run.
- No extra install needed — ``postup collect`` runs on the core-only
  ``buvis-gems`` install with zero tool-specific dependencies.
