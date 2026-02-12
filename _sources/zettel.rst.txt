Zettel
======

The zettel subsystem handles Zettelkasten note management — reading, formatting,
and syncing notes with external systems like Jira.

.. contents:: Table of Contents
   :local:
   :depth: 2

Core
----

Domain entities, use cases, and repository interfaces for Zettelkasten notes.

PrintZettelUseCase
~~~~~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.zettel.application.use_cases.print_zettel_use_case.PrintZettelUseCase
   :members:
   :undoc-members:
   :show-inheritance:

ReadZettelUseCase
~~~~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.zettel.application.use_cases.read_zettel_use_case.ReadZettelUseCase
   :members:
   :undoc-members:
   :show-inheritance:

Templates
---------

Templates define how ``bim create`` builds new zettels. Each template is a
Python module in ``src/lib/buvis/pybase/zettel/domain/templates/``. Drop a
module there and ``discover_templates()`` finds it automatically — no
registration needed.

Built-in templates: ``note`` (minimal, no questions) and ``project`` (asks for
dev type, creates project dir).

Writing a template
~~~~~~~~~~~~~~~~~~

A template is a class with three attributes/methods and a ``name`` class
variable:

.. code-block:: python

    # src/lib/buvis/pybase/zettel/domain/templates/meeting.py
    from __future__ import annotations

    from pathlib import Path
    from typing import Any

    from buvis.pybase.zettel.domain.templates import Hook, Question
    from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


    class MeetingTemplate:
        name = "meeting"

        def questions(self) -> list[Question]:
            return [
                Question(
                    key="attendees",
                    prompt="Attendees (comma-separated)",
                ),
                Question(
                    key="location",
                    prompt="Location",
                    choices=["office", "remote", "hybrid"],
                    default="remote",
                    required=True,
                ),
            ]

        def build_data(self, answers: dict[str, Any]) -> ZettelData:
            data = ZettelData()
            data.metadata["type"] = "meeting"
            data.metadata["title"] = answers.get("title", "")
            data.metadata["location"] = answers.get("location", "remote")
            data.metadata["attendees"] = answers.get("attendees", "")
            tags_raw = answers.get("tags", "")
            if tags_raw:
                data.metadata["tags"] = [
                    t.strip() for t in tags_raw.split(",") if t.strip()
                ]
            title = data.metadata["title"]
            data.sections = [
                (f"# {title}", ""),
                ("## Agenda", ""),
                ("## Notes", ""),
                ("## Action items", ""),
            ]
            return data

        def hooks(self) -> list[Hook]:
            return []

That's it. Save the file, and ``bim create -t meeting --title "Standup"``
works.

YAML templates
~~~~~~~~~~~~~~

You can also define templates as YAML files without writing Python. Place
``.yaml`` files in your config directory under ``templates/``:

- ``$BUVIS_CONFIG_DIR/templates/`` (highest priority)
- ``~/.config/buvis/templates/``
- ``~/.buvis/templates/``

A YAML template with the same ``name`` as a Python template overrides it.
Higher-priority config dirs override lower-priority ones.

Basic example
^^^^^^^^^^^^^

.. code-block:: yaml

    # ~/.config/buvis/templates/meeting.yaml
    name: meeting

    questions:
      - key: attendees
        prompt: "Who attended?"
        required: true
      - key: location
        prompt: "Location"
        default: "online"
        choices: ["online", "room-a", "room-b"]

    metadata:
      type: meeting
      attendees: "{attendees}"
      location: "{location}"

    sections:
      - heading: "# {title}"
        body: ""
      - heading: "## Agenda"
        body: ""
      - heading: "## Notes"
        body: ""
      - heading: "## Action items"
        body: ""

Usage:

.. code-block:: bash

    bim create -t meeting --title "Sprint review" -a attendees="Alice, Bob" -a location="room-a"

Field resolution
^^^^^^^^^^^^^^^^

Three resolution modes for metadata and section values:

**String substitution** — ``{key}`` is replaced with the answer value. Missing
keys become empty strings:

.. code-block:: yaml

    metadata:
      attendees: "{attendees}"
      note: "Created by {author}"     # empty string if author not provided

**Python eval** — a dict with an ``eval`` key runs arbitrary Python. All
answers are available as local variables:

.. code-block:: yaml

    metadata:
      tag_count:
        eval: "len(tags) if tags else 0"
      slug:
        eval: "title.lower().replace(' ', '-')"
      due:
        eval: "datetime.datetime.now() + datetime.timedelta(days=7)"

**Passthrough** — non-string, non-dict values (int, bool, list) are kept as-is:

.. code-block:: yaml

    metadata:
      completed: false
      priority: 3

Extending Python templates
^^^^^^^^^^^^^^^^^^^^^^^^^^

YAML templates can extend existing Python (or YAML) templates with ``extends``.
This lets you reuse base logic while customizing fields:

.. code-block:: yaml

    # ~/.config/buvis/templates/standup.yaml
    name: standup
    extends: note

    questions:
      - key: sprint
        prompt: "Sprint"

    metadata:
      type: standup
      sprint: "{sprint}"

    sections:
      - heading: "# {title}"
        body: ""
      - heading: "## Done"
        body: ""
      - heading: "## Doing"
        body: ""
      - heading: "## Blocked"
        body: ""

Inheritance rules:

- **Questions**: base questions appear first, YAML questions appended after
- **Metadata**: base metadata applied first, YAML keys overwrite or add
- **Sections**: if YAML defines ``sections``, they replace base sections entirely;
  otherwise base sections are kept
- **Hooks**: inherited from base (YAML can't define hooks)
- Single-level extends only (no chaining ``standup`` → ``note`` → something else)

Example extending ``project`` to inherit its directory-creation hook:

.. code-block:: yaml

    name: research-project
    extends: project

    questions:
      - key: hypothesis
        prompt: "Research hypothesis"

    metadata:
      type: project
      dev-type: spike
      hypothesis: "{hypothesis}"

Template protocol
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Member
     - Purpose
   * - ``name``
     - String used in ``-t/--type``. Must be unique across templates.
   * - ``questions()``
     - Returns ``list[Question]``. Each question becomes an input field in the
       TUI or a ``-a key=value`` flag in scripted mode. Return ``[]`` for no
       extra questions.
   * - ``build_data(answers)``
     - Receives a dict with ``title``, ``tags``, and any question keys.
       Returns a ``ZettelData`` with metadata and sections populated.
       Consistency defaults (date, id, publish, processed) are filled
       automatically by the Zettel entity — don't set them here.
   * - ``hooks()``
     - Returns ``list[Hook]``. Each hook runs after the file is written.
       Receives ``(ZettelData, zettelkasten_path)``. Return ``[]`` for no
       hooks.

Question fields
~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Field
     - Type
     - Description
   * - ``key``
     - ``str``
     - Answer key passed to ``build_data``. Also the ``-a`` flag name.
   * - ``prompt``
     - ``str``
     - Display text in TUI / help text.
   * - ``default``
     - ``Any``
     - Pre-filled value. Used as fallback in scripted mode when ``-a`` omits
       this key.
   * - ``choices``
     - ``list[str] | None``
     - If set, renders a select widget in TUI and validates input in scripted
       mode.
   * - ``required``
     - ``bool``
     - If ``True`` and no answer or default exists, scripted mode aborts.

Hook signature
~~~~~~~~~~~~~~

.. code-block:: python

    def my_hook(data: ZettelData, zettelkasten_path: Path) -> None:
        # data.metadata has the final zettel metadata (id, title, etc.)
        # zettelkasten_path is the resolved path to the zettelkasten dir
        ...

Wrap it in a ``Hook`` dataclass:

.. code-block:: python

    Hook(name="my_hook", fn=my_hook)

CLI usage
~~~~~~~~~

.. code-block:: bash

    # TUI (interactive wizard)
    bim create

    # TUI with template pre-selected
    bim create -t project

    # Scripted (non-interactive, requires both -t and --title)
    bim create -t note --title "My note" --tags "foo,bar"

    # With template-specific answers
    bim create -t project --title "Auth refactor" -a dev_type=spike

CreateZettelUseCase
~~~~~~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.zettel.application.use_cases.create_zettel_use_case.CreateZettelUseCase
   :members:
   :undoc-members:
   :show-inheritance:

Integrations
------------

Jira Assemblers
~~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.zettel.integrations.jira.assemblers.project_zettel_jira_issue.ProjectZettelJiraIssueDTOAssembler
   :members:
   :undoc-members:
   :show-inheritance:
