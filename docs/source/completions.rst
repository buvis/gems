Shell Completions
=================

All ``buvis-gems`` CLIs use Click, so each command can generate shell completion scripts on demand through its ``_<COMMAND>_COMPLETE`` environment variable.

Bash
----

Pattern:

.. code-block:: bash

    eval "$(_BIM_COMPLETE=bash_source bim)"

Commands:

.. code-block:: bash

    eval "$(_BIM_COMPLETE=bash_source bim)"
    eval "$(_DOT_COMPLETE=bash_source dot)"
    eval "$(_FCTRACKER_COMPLETE=bash_source fctracker)"
    eval "$(_FREN_COMPLETE=bash_source fren)"
    eval "$(_HELLO_WORLD_COMPLETE=bash_source hello-world)"
    eval "$(_MORPH_COMPLETE=bash_source morph)"
    eval "$(_MUC_COMPLETE=bash_source muc)"
    eval "$(_NETSCAN_COMPLETE=bash_source netscan)"
    eval "$(_OUTLOOKCTL_COMPLETE=bash_source outlookctl)"
    eval "$(_PUC_COMPLETE=bash_source puc)"
    eval "$(_PINGER_COMPLETE=bash_source pinger)"
    eval "$(_READERCTL_COMPLETE=bash_source readerctl)"
    eval "$(_SYSUP_COMPLETE=bash_source sysup)"
    eval "$(_VUC_COMPLETE=bash_source vuc)"
    eval "$(_ZSEQ_COMPLETE=bash_source zseq)"

Zsh
---

Pattern:

.. code-block:: zsh

    eval "$(_BIM_COMPLETE=zsh_source bim)"

Commands:

.. code-block:: zsh

    eval "$(_BIM_COMPLETE=zsh_source bim)"
    eval "$(_DOT_COMPLETE=zsh_source dot)"
    eval "$(_FCTRACKER_COMPLETE=zsh_source fctracker)"
    eval "$(_FREN_COMPLETE=zsh_source fren)"
    eval "$(_HELLO_WORLD_COMPLETE=zsh_source hello-world)"
    eval "$(_MORPH_COMPLETE=zsh_source morph)"
    eval "$(_MUC_COMPLETE=zsh_source muc)"
    eval "$(_NETSCAN_COMPLETE=zsh_source netscan)"
    eval "$(_OUTLOOKCTL_COMPLETE=zsh_source outlookctl)"
    eval "$(_PUC_COMPLETE=zsh_source puc)"
    eval "$(_PINGER_COMPLETE=zsh_source pinger)"
    eval "$(_READERCTL_COMPLETE=zsh_source readerctl)"
    eval "$(_SYSUP_COMPLETE=zsh_source sysup)"
    eval "$(_VUC_COMPLETE=zsh_source vuc)"
    eval "$(_ZSEQ_COMPLETE=zsh_source zseq)"

Fish
----

Pattern:

.. code-block:: fish

    _BIM_COMPLETE=fish_source bim | source

Commands:

.. code-block:: fish

    _BIM_COMPLETE=fish_source bim | source
    _DOT_COMPLETE=fish_source dot | source
    _FCTRACKER_COMPLETE=fish_source fctracker | source
    _FREN_COMPLETE=fish_source fren | source
    _HELLO_WORLD_COMPLETE=fish_source hello-world | source
    _MORPH_COMPLETE=fish_source morph | source
    _MUC_COMPLETE=fish_source muc | source
    _NETSCAN_COMPLETE=fish_source netscan | source
    _OUTLOOKCTL_COMPLETE=fish_source outlookctl | source
    _PUC_COMPLETE=fish_source puc | source
    _PINGER_COMPLETE=fish_source pinger | source
    _READERCTL_COMPLETE=fish_source readerctl | source
    _SYSUP_COMPLETE=fish_source sysup | source
    _VUC_COMPLETE=fish_source vuc | source
    _ZSEQ_COMPLETE=fish_source zseq | source

Persistent Setup
----------------

To keep completions after opening a new shell, add the command lines you use to your shell startup file:

- Bash: ``~/.bashrc``
- Zsh: ``~/.zshrc``
- Fish: ``~/.config/fish/config.fish``
