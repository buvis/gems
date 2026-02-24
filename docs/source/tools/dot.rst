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
