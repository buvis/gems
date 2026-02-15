.. _tool-outlookctl:

outlookctl
==========

Outlook calendar CLI. Windows only (uses COM automation via ``OutlookLocalAdapter``).

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``default_timeblock_duration``
     - ``25``
     - Timeblock duration in minutes (Pomodoro-style)

Commands
--------

outlookctl create_timeblock
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a timeblock event in Outlook.

.. code-block:: bash

    outlookctl create_timeblock
