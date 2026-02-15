.. _tool-hello-world:

hello-world
===========

Sample script template. Renders text with figlet fonts. Useful as a proof-of-concept
or starting point for new tools.

**Extra:** ``uv tool install buvis-gems[hello-world]``

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``font``
     - ``doom``
     - Figlet font name
   * - ``text``
     - ``World``
     - Text to render

Commands
--------

.. code-block:: bash

    hello-world                          # render "World" in doom font
    hello-world "Buvis" -f slant         # custom text and font
    hello-world -r                       # random font
    hello-world -l                       # list available fonts
    hello-world --diag                   # print python runtime and dep info

Options:

- ``-f, --font TEXT`` — font name
- ``-l, --list-fonts`` — list available fonts
- ``-r, --random-font`` — pick a random font
- ``--diag`` — print Python runtime and dependency info
