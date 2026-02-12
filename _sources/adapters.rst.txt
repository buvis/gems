Adapters
========

The adapters module wraps external tools and APIs behind consistent Python interfaces.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

- Wrap subprocess calls, COM automation, or REST APIs.
- `ShellAdapter.exe()` returns (stderr, stdout) tuples for standard shell operations.
- `UvToolManager.run()` exits the process directly after execution.
- Handle platform-specific differences internally.
- Log operations via the standard logging module.

Adapters differ in how they return results: shell wrappers yield `(stderr, stdout)` for post-processing, while `UvToolManager` terminates the process as part of its flow.

Return Convention
~~~~~~~~~~~~~~~~~

.. code-block:: python

    stderr, stdout = adapter.exe("command", working_dir)
    if stderr:
        # Handle error
    # Process stdout

When to Use
-----------

Choosing the Right Adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table:: Adapter Selection Guide
   :header-rows: 1
   :widths: 25 25 50

   * - Scenario
     - Adapter
     - Rationale
   * - New projects, fast installs
     - UvAdapter / UvToolManager
     - uv is faster than Poetry, better for CI/CD
   * - Running arbitrary shell commands
     - ShellAdapter
     - Handles aliases, env vars, logging
   * - JIRA issue creation
     - JiraAdapter
     - Typed DTO, handles custom field quirks
   * - Windows Outlook calendar
     - OutlookLocalAdapter
     - COM automation for local Outlook
   * - Styled terminal output
     - ConsoleAdapter
     - Rich formatting, spinners, confirmations

ShellAdapter vs Specific Adapters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Specific Adapters (JiraAdapter, OutlookLocalAdapter)
     - ShellAdapter
   * - Type-safe interfaces via DTOs
     - One-off commands without dedicated adapters
   * - API-specific error handling
     - Scripts requiring alias expansion
   * - Protocol abstraction (REST, COM)
     - Commands needing env var interpolation

API Reference
-------------

ShellAdapter
~~~~~~~~~~~~
Subprocess execution with alias and environment variable expansion.

.. autoclass:: buvis.pybase.adapters.ShellAdapter
   :members:
   :undoc-members:
   :show-inheritance:

ConsoleAdapter
~~~~~~~~~~~~~~~
Rich console output wrapper for styled terminal messages.

.. autoclass:: buvis.pybase.adapters.console.console.ConsoleAdapter
   :members:
   :undoc-members:
   :show-inheritance:

`console` singleton instance exposes the adapter for quick access.

.. autofunction:: buvis.pybase.adapters.logging_to_console

UvAdapter
~~~~~~~~~
Fast Python package manager integration with auto-installation.

.. autoclass:: buvis.pybase.adapters.UvAdapter
   :members:
   :undoc-members:
   :show-inheritance:

UvToolManager
~~~~~~~~~~~~~
Manage and run CLI tools installed via uv.

.. autoclass:: buvis.pybase.adapters.UvToolManager
   :members:
   :undoc-members:
   :show-inheritance:

JiraAdapter
~~~~~~~~~~~
JIRA REST API adapter for issue creation.

.. autoclass:: buvis.pybase.adapters.JiraAdapter
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: buvis.pybase.adapters.jira.domain.JiraIssueDTO
   :members:
   :show-inheritance:

Platform-Specific Adapters
~~~~~~~~~~~~~~~~~~~~~~~~~~

OutlookLocalAdapter
^^^^^^^^^^^^^^^^^^^

Windows-only adapter for local Outlook COM automation. Requires ``pywin32``
and a local Outlook installation. Only available when ``os.name == "nt"``.

.. note::
   This adapter cannot be autodocumented cross-platform as it raises ``OSError``
   on import when ``os.name != "nt"``.

**Methods:**

- ``__init__()``: Connect to local Outlook via COM. Initializes MAPI namespace and default calendar.
- ``create_timeblock(appointment_input: dict)``: Create a calendar appointment. Keys: ``subject``, ``body``, ``duration`` (minutes), ``location``, ``categories``, ``start`` (optional datetime).
- ``get_all_appointments()``: Retrieve all calendar appointments sorted by start time.
- ``get_day_appointments(appointments, date)``: Filter appointments to a single day.
- ``get_conflicting_appointment(desired_start, desired_duration, debug_level=0)``: Find appointment conflicting with proposed time slot.

**Example:**

.. code-block:: python

    # Windows only
    from buvis.pybase.adapters import OutlookLocalAdapter

    adapter = OutlookLocalAdapter()
    adapter.create_timeblock({
        "subject": "Check-in",
        "body": "Daily sync",
        "duration": 30,
        "location": "Desk",
        "categories": "Work"
    })

Examples
~~~~~~~~

ShellAdapter Example
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from pathlib import Path

    from buvis.pybase.adapters import ShellAdapter

    shell = ShellAdapter()
    shell.alias("lint", "poetry run lint")
    if not shell.is_command_available("git"):
        raise RuntimeError("git is required for this workflow")

    stderr, stdout = shell.exe("lint", Path("src"))
    if stderr:
        raise RuntimeError(f"lint failed: {stderr.strip()}")
    print(stdout)

ConsoleAdapter Example
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from buvis.pybase.adapters.console.console import console

    with console.status("Deploying service"):
        console.print("Gathering assets")
        if not console.confirm("Continue deployment?"):
            console.failure("Deployment aborted by user")
            raise SystemExit(1)
    console.success("Deployment finished")

JiraAdapter Example
^^^^^^^^^^^^^^^^^^^

Ensure configuration exposes ``server`` and ``token`` before instantiating the adapter.

.. code-block:: python

    from jira.exceptions import JIRAError
    from buvis.pybase.adapters import JiraAdapter
    from buvis.pybase.adapters.jira.domain import JiraIssueDTO

    cfg = MyConfig()  # supplies server, token, and optional proxy
    jira = JiraAdapter(cfg)
    issue = JiraIssueDTO(
        project="BUV",
        title="Document new adapter patterns",
        description="Describe adapter usage in docs",
        issue_type="Task",
        labels=["docs", "pybase"],
        priority="Medium",
        ticket="BUV-123",
        feature="adapter-workflows",
        assignee="alice",
        reporter="bob",
        team="platform",
        region="emea",
    )
    try:
        created = jira.create(issue)
        print(f"Issue created: {created.id} -> {created.link}")
    except JIRAError as e:
        print(f"JIRA API error: {e.status_code} - {e.text}")
        raise

UvAdapter Example
^^^^^^^^^^^^^^^^^

.. code-block:: python

    from buvis.pybase.adapters import UvAdapter

    # Ensure uv is installed and PATH is configured
    UvAdapter.ensure_uv()
    # uv is now available for subprocess calls
    # Use UvToolManager for running uv-managed tools

UvToolManager Example
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from pathlib import Path

    from buvis.pybase.adapters import UvToolManager

    project_root = Path("/project")
    # Directory layout:
    # /project
    # ├── bin/
    # └── src/
    #     └── my_tool/
    UvToolManager.install_all(project_root)
    UvToolManager.install_tool(project_root / "src" / "my_tool")
    UvToolManager.run(project_root / "bin" / "my-tool", ["--help"])  # exits on completion

