.. _tool-dot:

dot
===

Manager for bare-repo dotfiles. Wraps git operations on your ``$DOTFILES_ROOT``
(defaults to ``$HOME``).

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``add_file_path``
     - *none*
     - Default file to stage in ``add``
   * - ``confirm_revert``
     - ``true``
     - Show confirmation modal before reverting a hunk or selected lines (``r``). Set to ``false`` to skip the prompt.
   * - ``remote_url``
     - *none*
     - Remote URL that ``dot setup`` clones when no URL argument is given (``BUVIS_DOT_REMOTE_URL``).

Commands
--------

dot (TUI)
~~~~~~~~~

Launch the interactive TUI for managing dotfiles. Shows unstaged and staged
files with diff preview, supports keyboard navigation and staging/unstaging.

.. code-block:: bash

    dot                         # launches TUI (default when no subcommand)
    dot tui                     # explicit TUI launch

**Keybindings:**

- ``j``/``k`` - navigate file lists (in file pane), navigate hunks (in diff pane)
- ``Tab`` - cycle focus between Unstaged, Staged, and Diff panes
- ``s`` / ``Space`` - stage focused file (from Unstaged pane)
- ``u`` / ``Space`` - unstage focused file (from Staged pane)
- ``Enter`` - stage/unstage focused hunk (in diff pane)
- ``v`` - enter line-select mode (in diff pane, on focused hunk)
- ``j``/``k`` - navigate changed lines (in line-select mode)
- ``Space`` - toggle line selection (in line-select mode)
- ``Enter`` - stage selected lines (in line-select mode)
- ``r`` - revert focused hunk (in diff pane, unstaged view) or selected lines (in line-select mode); confirm by default. No-op on the staged view.
- ``Escape`` - exit line-select mode
- ``c`` - commit staged files (opens message input)
- ``d`` - delete tracked file (with confirmation)
- ``i`` - add file to .gitignore (opens pattern input)
- ``p`` - push commits to remote
- ``P`` (shift+p) - pull from remote with submodule update
- ``b`` - open file browser (browse untracked files, add to tracking)
- ``S`` (shift+s) - open secrets panel (manage git-secret files)
- ``e`` - quick encrypt (register focused file with git-secret)
- ``r`` (in file panes) - hide (re-encrypt) modified secrets, then refresh all panes
- ``L`` (shift+l) - relink missing host-specific config links
- ``q`` - quit

**Browse view** (``b``):

- ``j``/``k`` - navigate entries
- ``Enter`` - drill into directory
- ``Backspace`` - go to parent directory
- ``a`` - add untracked file to tracking
- ``i`` - add file to .gitignore
- ``e`` - register file with git-secret
- ``Escape`` - return to main view

**Secrets panel** (``S``):

- ``j``/``k`` - navigate secret list
- ``r`` - reveal all secrets (decrypt)
- ``h`` - hide all secrets (encrypt)
- ``E`` (shift+e) - unregister secret (with confirmation)
- ``Escape`` - return to main view

Requires the ``dot`` extra: ``pip install buvis-gems[dot]``

dot setup
~~~~~~~~~

Bring up dotfiles on a fresh host. Give the remote URL as an argument, or set
``BUVIS_DOT_REMOTE_URL``. The argument wins when both are set.

.. code-block:: bash

    dot setup git@host:me/dotfiles.git
    dot setup                   # uses BUVIS_DOT_REMOTE_URL

Steps:

#. Bare-clone the remote into ``<dotfiles_root>/.buvis``.
#. Hide untracked files from ``git status`` (``status.showUntrackedFiles no``).
#. Set the upstream of the checked-out branch to ``origin/<branch>``. A failure
   is a warning, and setup continues.
#. Check out the files into ``<dotfiles_root>``.
#. Link host config and install the git hooks, like ``dot materialize``.

``dot setup`` refuses when ``<dotfiles_root>/.buvis`` already exists or when the
clone fails. The checkout never overwrites anything: if existing files conflict,
setup stops and lists them. Move those files away, then run
``dot run checkout`` and ``dot materialize`` (to install any missing hooks).

dot status
~~~~~~~~~~

Hides (re-encrypts) modified secrets, then shows staged and unstaged changes
in your dotfiles repo. Uses ``git status --porcelain`` and labels each file
as ``staged`` or ``unstaged``.

.. code-block:: bash

    dot status

If the ``host-links`` manifest has problems, ``dot status`` reports them too.
See `Host-specific config`_. Status also warns ``hooks dir missing`` or
``pre-commit hook missing`` when the configured ``core.hooksPath`` points at a
missing directory or at one without a ``pre-commit`` hook.

dot materialize
~~~~~~~~~~~~~~~

Create the host-specific config links listed in the ``host-links`` manifest.
See `Host-specific config`_.

.. code-block:: bash

    dot materialize             # create missing links, install git hooks
    dot materialize --hook      # quiet mode used by the git hooks

dot run
~~~~~~~

Run any git command against the dotfiles bare repo. Everything after ``run``
is appended to the ``cfg`` alias.

.. code-block:: bash

    dot run log --oneline -5    # recent commits
    dot run diff                # unstaged changes
    dot run remote -v           # list remotes
    dot run stash list          # list stashes
    dot run submodule update --init

dot add
~~~~~~~

Stage changes. A tracked file or a directory opens git's hunk picker
(``add -p``); a file the repository has never tracked is added whole. A path is
looked up relative to the current directory first, then relative to the
dotfiles root; one found in neither place is an error, and a symlink is staged
as the link itself. An ignored file is refused with the matching ignore rule
and the ``git add -f`` command that overrides it. Afterwards the command prints
what is currently staged for the path, or warns when nothing is.

.. code-block:: bash

    dot add                     # hunk picker over the whole tree
    dot add ~/.bashrc           # hunk picker for a tracked file
    dot add config.yml          # new file, relative to the current directory

dot unstage
~~~~~~~~~~~

Remove files from the staging area without touching local changes.

.. code-block:: bash

    dot unstage                 # unstage all
    dot unstage .bashrc         # unstage specific file

dot commit
~~~~~~~~~~

Commit staged dotfiles changes. Message is a positional argument.

.. code-block:: bash

    dot commit "update shell config"

dot rm
~~~~~~

Remove a file from dotfiles tracking, keeping the file on disk. ``rm`` untracks;
``delete`` is the command that removes a file from disk.

For encrypted files, ``rm`` unregisters the file from git-secret and untracks the
committed ``<file>.secret`` ciphertext. The decrypted plaintext stays on disk and
keeps its ``.gitignore`` entry, so the cleartext secret is not offered for staging
by the next ``dot add``. Cleaning up that ignore entry belongs to ``dot delete``.

.. code-block:: bash

    dot rm .bashrc                  # stop tracking (file stays on disk)
    dot rm .config/secrets.yaml     # unregister encrypted file (plaintext kept)

dot delete
~~~~~~~~~~

Delete a file from dotfiles tracking and disk. For encrypted files, handles
full git-secret cleanup. For normal files, uses ``cfg rm`` which removes from
both tracking and disk.

.. code-block:: bash

    dot delete .bashrc              # remove from tracking and disk
    dot delete .config/secrets.yaml # delete encrypted file entirely

dot encrypt
~~~~~~~~~~~

Register a file for git-secret encryption.

.. code-block:: bash

    dot encrypt ~/.config/secrets.yaml

dot pull
~~~~~~~~

Pull dotfiles and update submodules. Reveals git-secret files if available.

Before merging, ``dot pull`` detects incoming deletions of host-link targets
and rescues your local bytes. When the upstream manifest defines a target that
incoming commits delete, dot moves your local target to the source location
(or backs up one side when both exist with different content).

**Collision handling:**

When the target and source both exist and differ, you must choose:

- **keep-source**: Keep the existing source file, backup the target
- **keep-target**: Keep the target's bytes as the new source, backup old source
- **cancel**: Abort the pull, nothing changes

In a TTY, ``dot pull`` prompts for each collision. Non-interactive runs fail
with ``pull stopped: unresolved host-link collision(s): <targets>``.

The TUI (``P``) shows a modal for each collision with keys ``s``/``t``/``Esc``.

.. warning::

   Raw ``git pull`` bypasses rescue - git has no pre-pull hook. Always use
   ``dot pull`` to protect host-specific files.

.. code-block:: bash

    dot pull

dot localize
~~~~~~~~~~~~

Convert a tracked file or directory to a host-specific link. This automates
the manual steps described in "First setup": untrack, move, link, manifest.

.. code-block:: bash

    dot localize .config/gita/repos.csv                    # default source: .local/.config/gita/repos.csv
    dot localize .bashrc --to .host-config/.bashrc         # custom source path

**What it does:**

1. Untracks the file from git (if tracked)
2. Moves the file to the source location
3. Creates a symlink at the original path pointing to the source
4. Appends an entry to the host-links manifest
5. Stages the manifest

**Refusals:**

- Target doesn't exist
- Target is already a symlink
- Source path already exists
- Target already in manifest
- Any tracked file under target is a git-secret file

After localizing, commit the staged manifest and the deletion. On other hosts,
``dot pull`` will rescue their local bytes before the deletion is applied.

dot push
~~~~~~~~

Push dotfiles to remote.

.. code-block:: bash

    dot push

Host-specific config
--------------------

Some config differs per host. Keep each host's real file next to the target,
untracked, and link it into place with a tracked manifest.

The manifest is ``<dotfiles_root>/.config/buvis/host-links``. Track it in the
dotfiles repo. Each line has the form ``<target> => <source>``. Both sides are
relative to ``$HOME`` and use ``/`` as separator. Blank lines and lines whose
first non-space character is ``#`` are skipped. Absolute paths, ``~``, drive
letters and ``..`` are rejected with ``host-links:<lineno>: <reason>``. Dot
skips the bad line and reads the rest.

.. code-block:: text

    # target => source
    .config/gita/repos.csv => .config/gita/repos.csv.host
    .config/git/local.conf => .config/git/local.conf.host

``dot materialize [--hook]`` creates each missing link ``target -> source``,
using an absolute source path. It never deletes or overwrites anything. It
warns about real files, wrong links, dangling links and missing sources.

Without ``--hook``, ``dot materialize`` also installs the missing
``post-checkout``, ``post-merge`` and ``post-rewrite`` hooks into git
``core.hooksPath``, when that is set. It never changes an existing hook file.
If one of those hooks already exists and is not dot's, links are not refreshed
on that git event, and dot does not report it. Call ``dot materialize --hook``
from that hook yourself.
The hooks run ``dot materialize --hook`` with ``BUVIS_AUTO_UPDATE=false``.
With ``--hook``, dot makes no git calls and always exits 0.

``dot status`` and the TUI report link problems. The TUI status bar shows
``<n> link problem(s)``. Press ``L`` to relink.

On Windows, directories become junctions. File links need symlink rights, so
enable Developer Mode. Otherwise dot reports ``symlink refused; enable
Developer Mode``. The hooks need ``python3`` on ``PATH``.

First setup
~~~~~~~~~~~

Every dot command that touches git sets ``core.hooksPath`` to
``<dotfiles_root>/.config/buvis/hooks`` when it is unset. It never changes a
value that is already set. ``dot status`` warns ``hooks dir missing: <dir>`` or
``pre-commit hook missing: <dir>/pre-commit`` when the hooks are not in place.
On a new host, run ``dot setup <url>``.

To make a file that the dotfiles repo already tracks host-specific, use
``dot localize``:

.. code-block:: bash

    dot localize .config/gita/repos.csv
    dot commit "Localize repos.csv"
    dot push

On other hosts, ``dot pull`` automatically rescues their local bytes to the
source location and creates the link.

**Manual method** (before ``dot localize`` existed):

.. code-block:: bash

    git --git-dir=$HOME/.buvis --work-tree=$HOME rm --cached .config/gita/repos.csv
    mv ~/.config/gita/repos.csv ~/.config/gita/repos.csv.host
    echo ".config/gita/repos.csv => .config/gita/repos.csv.host" >> ~/.config/buvis/host-links
    dot materialize
    dot status

Commit the removal and the manifest together.

.. warning::

   Raw ``git pull`` bypasses rescue - git has no pre-pull hook. Always use
   ``dot pull`` to protect host-specific files.
