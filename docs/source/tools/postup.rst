.. _tool-postup:

postup
======

**PO**\ rtfolio **ST**\ and\ **UP** — a portfolio standup gem. ``postup`` gathers
the state of every repository in your portfolio into typed, versioned file
contracts that the other postup interfaces consume. It runs fully without any
LLM.

This page documents PRD A (the gem scaffold and deterministic collector),
PRD B (optional LLM enrichment via the ``claude`` CLI), and PRD F (the terminal
standup surfaces — the text brief and the Textual TUI). The web UI lands in a
later PRD.

Usage
-----

.. code-block:: bash

    postup collect               # collect every configured repo, fetch first
    postup collect --no-fetch    # skip 'git fetch' (fast path, offline-ish)
    postup collect --days 30     # narrow the commit window (default 60)
    postup enrich                # optional: add narrative/epics/todos via claude
    postup                       # print the text standup (bare = brief)
    postup brief                 # print the text standup (explicit)
    postup tui                   # open the interactive Textual standup

``postup collect`` discovers repositories, gathers their signals in parallel,
and writes four file contracts under the output directory. A repository whose
data cannot be gathered (``gh`` unauthenticated, a network hiccup, an odd repo
state) degrades into that repository's ``errors`` list and a console warning —
the run never crashes and always exits successfully as long as at least one
repository was discovered.

``postup enrich`` is an optional second step that turns the collected data into
a model-authored ``epics.json``. It is described under *Enrichment* below.

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
    model: null                           # optional Claude model for enrich

============  ==================================================================
Setting       Meaning
============  ==================================================================
``roots``     Directories scanned recursively for ``.git`` repositories. A
              directory holding ``.git`` is a repository and the scan stops
              descending into it.
``excludes``  Absolute repository paths dropped from the discovered set.
``out_dir``   Output directory for the file contracts. Defaults to the XDG data
              dir ``~/.local/share/postup``.
``model``     Optional Claude model name for ``postup enrich``. Unset uses the
              ``claude`` CLI's own default model.
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

Enrichment
----------

``postup enrich`` is a strictly optional step that shells out to the ``claude``
CLI to add the model-authored portion of the brief — a manager-voice narrative
summary, per-repository epics grouping commits by theme, and a handful of
judgment todos — writing them to ``epics.json`` beside the collected contracts.

.. code-block:: bash

    postup enrich    # reads data.json + commits-digest.md, writes epics.json

Behaviour:

- **Availability** is detected before any prompt is built. When ``claude`` is on
  ``PATH`` the run announces which mode and model it will use; when it is absent
  the run **warns that quality suffers, continues, and exits successfully** —
  enrichment never blocks the deterministic brief.
- **Model** — the ``model`` setting is passed to ``claude`` only when set;
  otherwise the ``claude`` CLI's own default model is used. postup never pins a
  model.
- **Validation** — the model's JSON is validated against the epics schema, and
  every epic commit SHA is cross-checked against the collected commit set so a
  hallucinated reference is rejected, not written. On a parse or validation
  failure the command retries **exactly once** with the errors appended to the
  prompt; a second failure warns and continues **without writing a partial
  file**.
- **Stable ids** — each judgment todo's id is derived deterministically from its
  repository and action, so done-state tracking survives re-enrichment.
- **Stale-input guard** — a missing ``data.json`` is the one hard failure: the
  command reports that you must run ``postup collect`` first.

``epics.json`` carries its own ``schema_version``, a ``summary`` string, a
``repos`` map of per-repo epics (each with a ``title``, ``summary``, and exact
``shas``), and a ``todos`` list (``id``, ``repo``, ``urgency``, ``action``,
``why``, plus optional ``importance`` and ``effort``). It is written atomically
alongside the collector's contracts. No cloud AI SDK and no extra Python
dependency are involved — the ``claude`` binary on ``PATH`` is the entire LLM
integration.

Terminal standup
----------------

``postup`` renders a deterministic terminal standup on two surfaces — a plain
text brief and an interactive Textual TUI — both driven by **one** Python derive
layer (``postup.domain.derive``), so the CLI and TUI show identical facts for the
same data (the all-interface rule). The derive layer is pure and UI-free: it
imports neither Textual nor Click, reads only the file contracts, and never
raises on missing inputs.

Text brief (the default)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Bare ``postup`` (and the explicit ``postup brief``) print the standup from the
latest ``data.json``:

.. code-block:: bash

    postup            # bare postup == the text brief
    postup brief      # the same surface, explicit

The brief shows a ranked **attention queue** (failing CI, security alerts, open
PRs, long-dirty checkouts, idle WIP PRDs, and portfolio-external review
requests), **mechanical todos** derived deterministically from the signals (cut
a release, fix failing CI, prune merged branches), a **per-repo summary** row,
and the **since-last diff** against the previous run. Judgment todos and the
narrative summary appear only when ``epics.json`` exists (i.e. after
``postup enrich``); otherwise a one-line *not enriched* cue is shown. This path
imports **no Textual** and runs on the core-only install — enforced by an
import-isolation test, not convention. A missing ``data.json`` prints a friendly
*run postup collect first* message, never a traceback.

Textual TUI
~~~~~~~~~~~

``postup tui`` opens the interactive standup — attention queue, todos, and repo
list — as a read-only view over the **same** derive output as the text brief:

.. code-block:: bash

    postup tui        # requires the 'postup' extra (Textual)

The TUI needs the ``postup`` extra (Textual). When it is absent the command
reports a standardized install hint (``uv tool install buvis-gems[postup]``)
rather than a traceback. Its layout is gated by Textual snapshot tests that run
only on the canonical CI env (Linux + Python 3.12) and are auto-skipped
elsewhere; regenerate baselines via the ``update-snapshots`` GitHub workflow.


- An authenticated ``gh`` CLI for forge data. Its absence degrades per
  repository into ``errors`` rather than failing the run.
- The ``claude`` CLI on ``PATH`` for ``postup enrich`` only. Its absence makes
  enrichment a no-op warning — ``postup collect`` and every deterministic
  surface are unaffected.
- No extra needed for ``postup collect`` and the text brief — they run on the
  core-only ``buvis-gems`` install with zero tool-specific dependencies. The
  ``postup`` extra (Textual) is required **only** for ``postup tui``:
  ``uv tool install buvis-gems[postup]``.
