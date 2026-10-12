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

dot status
~~~~~~~~~~

Hides (re-encrypts) modified secrets, then shows staged and unstaged changes
in your dotfiles repo. Uses ``git status --porcelain`` and labels each file
as ``staged`` or ``unstaged``.

.. code-block:: bash

    dot status

If the ``host-links`` manifest has problems, ``dot status`` reports them too.
See `Host-specific config`_.

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

Interactively stage changes (cherry-pick mode).

.. code-block:: bash

    dot add                     # interactive selection
    dot add ~/.bashrc           # stage specific file

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

.. code-block:: bash

    dot pull

dot push
~~~~~~~~

Push dotfiles to remote.

.. code-block:: bash

    dot push

Host-specific config
--------------------

Some config differs per host. Keep the host files in the repo and link them
into place with a manifest.

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
The hooks run ``dot materialize --hook`` with ``BUVIS_AUTO_UPDATE=false``.
With ``--hook``, dot makes no git calls and always exits 0.

``dot status`` and the TUI report link problems. The TUI status bar shows
``<n> link problem(s)``. Press ``L`` to relink.

On Windows, directories become junctions. File links need symlink rights, so
enable Developer Mode. Otherwise dot reports ``symlink refused; enable
Developer Mode``. The hooks need ``python3`` on ``PATH``.
