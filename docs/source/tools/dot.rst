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
- ``Escape`` - exit line-select mode
- ``c`` - commit staged files (opens message input)
- ``d`` - delete tracked file (with confirmation)
- ``i`` - add file to .gitignore (opens pattern input)
- ``p`` - push commits to remote
- ``P`` (shift+p) - pull from remote with submodule update
- ``b`` - open file browser (browse untracked files, add to tracking)
- ``S`` (shift+s) - open secrets panel (manage git-secret files)
- ``e`` - quick encrypt (register focused file with git-secret)
- ``r`` - refresh all panes
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

Show staged and unstaged changes in your dotfiles repo. Uses ``git status
--porcelain`` and labels each file as ``staged`` or ``unstaged``.

.. code-block:: bash

    dot status

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

Remove a file from dotfiles tracking. Detects whether the file is encrypted
by git-secret and handles cleanup accordingly: encrypted files go through
full git-secret removal (untrack, clean ``.gitignore``, delete plaintext),
normal files use standard ``cfg rm``.

.. code-block:: bash

    dot rm .bashrc                  # remove unencrypted file
    dot rm .config/secrets.yaml     # remove encrypted file

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
