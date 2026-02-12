Configuration
=============

This module provides unified configuration management for BUVIS tools with
automatic precedence handling across multiple sources.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

The configuration system loads settings from multiple sources with clear
precedence rules:

1. **CLI arguments** (highest priority)
2. **Environment variables** (``BUVIS_*`` prefix)
3. **YAML config files** (auto-discovered)
4. **Model defaults** (lowest priority)

This means a ``--debug`` flag always wins over ``BUVIS_DEBUG=false`` in the
environment, which wins over ``debug: false`` in a YAML file.

Source Mapping
~~~~~~~~~~~~~~

Each Python field maps to CLI, ENV, and YAML sources with consistent naming:

.. list-table:: Mapping Example for ``PhotoSettings``
   :header-rows: 1
   :widths: 25 25 25 25

   * - Python Field
     - CLI Argument
     - Environment Variable
     - YAML Path
   * - ``debug``
     - ``--debug``
     - ``BUVIS_PHOTO_DEBUG``
     - ``photo.debug``
   * - ``log_level``
     - ``--log-level``
     - ``BUVIS_PHOTO_LOG_LEVEL``
     - ``photo.log_level``
   * - ``library_path``
     - (custom option)
     - ``BUVIS_PHOTO_LIBRARY_PATH``
     - ``photo.library_path``
   * - ``db.host`` (nested)
     - (custom option)
     - ``BUVIS_PHOTO__DB__HOST``
     - ``photo.db.host``

**Naming rules:**

- **CLI**: Built-in options (``--debug``, ``--log-level``) are added automatically. Custom fields require explicit Click options - see `Adding Custom CLI Options`_ below.
- **ENV**: Prefix from ``env_prefix`` + field name in SCREAMING_SNAKE_CASE. Nested fields use ``__`` delimiter.
- **YAML**: Tool name (derived from prefix) as root key, then field names with ``.`` for nesting.

Adding Custom CLI Options
~~~~~~~~~~~~~~~~~~~~~~~~~

The ``@buvis_options`` decorator only adds ``--debug``, ``--log-level``,
``--config-dir``, and ``--config``. For custom fields, add your own Click
options and pass them to ``cli_overrides``:

.. code-block:: python

    import click
    from buvis.pybase.configuration import ConfigResolver, GlobalSettings
    from pydantic_settings import SettingsConfigDict
    from pathlib import Path

    class PhotoSettings(GlobalSettings):
        model_config = SettingsConfigDict(env_prefix="BUVIS_PHOTO_")
        library_path: Path = Path.home() / "Pictures"
        quality: int = 85

    @click.command()
    @click.option("--library", type=click.Path(exists=True), help="Photo library path")
    @click.option("--quality", type=int, help="JPEG quality (1-100)")
    @click.option("--debug/--no-debug", default=None)
    def main(library: str | None, quality: int | None, debug: bool | None) -> None:
        cli_overrides = {
            k: v for k, v in {
                "library_path": Path(library) if library else None,
                "quality": quality,
                "debug": debug,
            }.items() if v is not None
        }

        resolver = ConfigResolver()
        settings = resolver.resolve(PhotoSettings, cli_overrides=cli_overrides)
        click.echo(f"Library: {settings.library_path}")

For nested fields (e.g., ``db.host``), flatten them in cli_overrides:

.. code-block:: python

    # Nested settings don't have direct CLI support in cli_overrides.
    # Use ENV vars or YAML for nested fields, or restructure as top-level.

Tool-Specific Configuration Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can separate tool configuration from global settings using dedicated files.
The loader searches for both ``buvis.yaml`` AND ``buvis-{tool}.yaml``:

**Option 1: Section in global file**

.. code-block:: yaml

    # ~/.config/buvis/buvis.yaml
    debug: false
    log_level: INFO

    photo:                    # Tool section (from BUVIS_PHOTO_ prefix)
      library_path: /media/photos
      quality: 90

**Option 2: Separate tool file**

.. code-block:: yaml

    # ~/.config/buvis/buvis-photo.yaml
    library_path: /media/photos
    quality: 90

Both are merged. Tool-specific file values override global file values for that tool.

The tool name is derived from ``env_prefix``:

- ``BUVIS_PHOTO_`` → searches for ``buvis-photo.yaml`` and ``photo:`` section
- ``BUVIS_`` (default) → only ``buvis.yaml``, no tool section

**Complete example:**

.. code-block:: python

    from buvis.pybase.configuration import GlobalSettings, ToolSettings
    from pydantic_settings import SettingsConfigDict
    from pathlib import Path

    class DatabaseSettings(ToolSettings):
        host: str = "localhost"
        port: int = 5432

    class PhotoSettings(GlobalSettings):
        model_config = SettingsConfigDict(
            env_prefix="BUVIS_PHOTO_",
            env_nested_delimiter="__",
        )
        library_path: Path = Path.home() / "Pictures"
        db: DatabaseSettings = DatabaseSettings()

All equivalent ways to set ``db.host`` to ``"prod.db.local"``:

.. code-block:: bash

    # Environment variable (note double underscore for nesting)
    export BUVIS_PHOTO__DB__HOST=prod.db.local

.. code-block:: yaml

    # YAML (~/.config/buvis/buvis.yaml)
    photo:
      db:
        host: prod.db.local

.. code-block:: python

    # Python default
    class DatabaseSettings(ToolSettings):
        host: str = "prod.db.local"

Quick Start
-----------

Add configuration to any Click command:

.. code-block:: python

    import click
    from buvis.pybase.configuration import buvis_options, get_settings

    @click.command()
    @buvis_options
    @click.pass_context
    def main(ctx: click.Context) -> None:
        settings = get_settings(ctx)
        if settings.debug:
            click.echo("Debug mode enabled")
        click.echo(f"Log level: {settings.log_level}")

    if __name__ == "__main__":
        main()

This adds ``--debug``, ``--log-level``, ``--config-dir``, and ``--config``
options. Values resolve from CLI > ENV > YAML > defaults.

For tool-specific settings, see `Downstream Project Integration`_ or
`Custom Settings Classes`_.

Downstream Project Integration
------------------------------

Step-by-step guide for projects depending on buvis-pybase.

Step 1: Define Settings
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # myproject/settings.py
    from buvis.pybase.configuration import GlobalSettings
    from pydantic_settings import SettingsConfigDict
    from pathlib import Path

    class MyProjectSettings(GlobalSettings):
        model_config = SettingsConfigDict(
            env_prefix="MYPROJECT_",
            env_nested_delimiter="__",
        )
        data_dir: Path = Path.home() / ".myproject"
        verbose: bool = False

Step 2: Wire CLI
~~~~~~~~~~~~~~~~

.. code-block:: python

    # myproject/cli.py
    import click
    from buvis.pybase.configuration import buvis_options, get_settings
    from myproject.settings import MyProjectSettings

    @click.command()
    @buvis_options(settings_class=MyProjectSettings)
    @click.pass_context
    def main(ctx: click.Context) -> None:
        settings = get_settings(ctx, MyProjectSettings)
        if settings.verbose:
            click.echo(f"Data dir: {settings.data_dir}")

Step 3: Configure (any combination)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CLI: ``myproject --debug --log-level DEBUG``

Environment:

.. code-block:: bash

    export MYPROJECT_DATA_DIR=/var/data
    export MYPROJECT_VERBOSE=true

YAML (``~/.config/buvis/buvis.yaml``):

.. code-block:: yaml

    myproject:
      data_dir: /var/data
      verbose: true

Example: Abbreviations from Config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Load abbreviation definitions from YAML and pass to ``StringOperator``:

.. code-block:: python

    from buvis.pybase.configuration import GlobalSettings, ToolSettings
    from buvis.pybase.formatting import StringOperator
    from pydantic_settings import SettingsConfigDict

    class FormattingSettings(ToolSettings):
        abbreviations: list[dict] = []

    class DocSettings(GlobalSettings):
        model_config = SettingsConfigDict(env_prefix="DOC_")
        formatting: FormattingSettings = FormattingSettings()

    # In CLI:
    settings = get_settings(ctx, DocSettings)
    expanded = StringOperator.replace_abbreviations(
        text="Use the API",
        abbreviations=settings.formatting.abbreviations,
        level=1,
    )  # -> "Use the Application Programming Interface"

YAML:

.. code-block:: yaml

    doc:
      formatting:
        abbreviations:
          - API: Application Programming Interface
          - CLI: Command Line Interface

YAML Configuration
------------------

File Locations
~~~~~~~~~~~~~~

Config files are discovered in order (first found wins):

1. ``$BUVIS_CONFIG_DIR/buvis.yaml`` (if env var set)
2. ``$XDG_CONFIG_HOME/buvis/buvis.yaml`` (or ``~/.config/buvis/buvis.yaml``)
3. ``~/.buvis/buvis.yaml`` (legacy)
4. ``./buvis.yaml`` (current directory)

For tool-specific config, files named ``buvis-{tool}.yaml`` are also checked.

File Format
~~~~~~~~~~~

.. code-block:: yaml

    # ~/.config/buvis/buvis.yaml
    debug: false
    log_level: INFO
    output_format: text

    # Tool-specific sections
    photo:
      watermark: true
      default_album: shared
    music:
      normalize: true
      bitrate: 320

Environment Variable Substitution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

YAML files support environment variable interpolation:

.. code-block:: yaml

    database:
      host: ${DB_HOST}                    # Required - fails if not set
      port: ${DB_PORT:-5432}              # Optional with default
      password: ${DB_PASSWORD}
      connection_string: $${NOT_EXPANDED} # Escaped - becomes literal ${NOT_EXPANDED}

Substitution is applied automatically by ``ConfigResolver`` when it loads YAML:

.. code-block:: python

    from buvis.pybase.configuration import ConfigResolver
    from myapp.settings import PhotoSettings

    resolver = ConfigResolver()
    settings = resolver.resolve(PhotoSettings)

Environment Variables
---------------------

The ``GlobalSettings`` base class uses the ``BUVIS_`` prefix in
SCREAMING_SNAKE_CASE. Override ``env_prefix`` on your settings class (as shown
in ``PhotoSettings`` above) to scope variables per tool:

.. code-block:: bash

    export BUVIS_PHOTO_DEBUG=true
    export BUVIS_PHOTO_LOG_LEVEL=DEBUG
    export BUVIS_PHOTO_OUTPUT_FORMAT=json

For nested fields, use double underscores:

.. code-block:: bash

    export BUVIS_PHOTO__MUSIC__NORMALIZE=true
    export BUVIS_PHOTO__MUSIC__BITRATE=256

Custom Settings Classes
-----------------------

GlobalSettings vs ToolSettings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the right base class:

- **GlobalSettings** (``pydantic_settings.BaseSettings``) - For your root settings class. Loads from environment variables automatically using the ``env_prefix``.
- **ToolSettings** (``pydantic.BaseModel``) - For nested settings within a root class. Does NOT load from env directly; the parent ``GlobalSettings`` handles env resolution for nested fields.

.. code-block:: python

    from buvis.pybase.configuration import GlobalSettings, ToolSettings

    # ToolSettings for nested - no env loading, just structure
    class DatabaseSettings(ToolSettings):
        host: str = "localhost"
        port: int = 5432

    # GlobalSettings for root - loads BUVIS_MYAPP_* from env
    class MyAppSettings(GlobalSettings):
        model_config = SettingsConfigDict(env_prefix="BUVIS_MYAPP_")
        db: DatabaseSettings = DatabaseSettings()  # Nested

    # Environment variable for nested field:
    # BUVIS_MYAPP__DB__HOST=prod.db.local  (double underscore!)

**Why this matters**: If you used ``GlobalSettings`` for nested classes, each would try to load from env independently with potentially conflicting prefixes.

Both classes are **frozen** (immutable) - you cannot modify settings after creation:

.. code-block:: python

    settings = get_settings(ctx, MyAppSettings)
    settings.db.host = "other"  # Raises: ValidationError (frozen)

Composing Settings
~~~~~~~~~~~~~~~~~~

Model tool namespaces with ``ToolSettings`` and compose them into your root
``GlobalSettings`` subclass:

.. code-block:: python

    from typing import Literal
    from buvis.pybase.configuration import GlobalSettings, ToolSettings
    from pydantic_settings import SettingsConfigDict

    class MusicSettings(ToolSettings):
        normalize: bool = True
        bitrate: int = 320

    class PhotoSettings(GlobalSettings):
        model_config = SettingsConfigDict(
            env_prefix="BUVIS_PHOTO_",
            env_nested_delimiter="__",
        )
        resolution: Literal["low", "medium", "high"] = "high"
        watermark: bool = False
        music: MusicSettings = MusicSettings()

Nested environment variables map to these namespaces (for example,
``BUVIS_PHOTO__RESOLUTION=medium`` or ``BUVIS_PHOTO__MUSIC__BITRATE=256``).

Using ConfigResolver Directly
-----------------------------

For non-Click applications or custom resolution:

.. code-block:: python

    from buvis.pybase.configuration import ConfigResolver
    from myapp.settings import PhotoSettings

    resolver = ConfigResolver()
    settings = resolver.resolve(
        PhotoSettings,
        cli_overrides={"debug": True},  # Simulate CLI args
    )

    # Check where each value came from
    print(resolver.sources)  # {"debug": ConfigSource.CLI, "log_level": ConfigSource.DEFAULT}

Security Considerations
-----------------------

Sensitive Fields
~~~~~~~~~~~~~~~~

Fields matching patterns like ``password``, ``token``, ``api_key``, ``secret``
are automatically:

- Masked in ``__repr__`` output (shows ``***``)
- Logged at INFO level (vs DEBUG for normal fields)
- Hidden in validation error messages

.. code-block:: python

    from buvis.pybase.configuration import SafeLoggingMixin
    from pydantic_settings import BaseSettings

    class SecureSettings(SafeLoggingMixin, BaseSettings):
        api_key: str
        password: str

    s = SecureSettings(api_key="secret123", password="hunter2")
    print(s)  # SecureSettings(api_key='***', password='***')

JSON Size Limits
~~~~~~~~~~~~~~~~

Environment variables containing JSON are limited to 64KB to prevent DoS:

.. code-block:: python

    from buvis.pybase.configuration import SecureSettingsMixin
    from pydantic_settings import BaseSettings

    class MySettings(SecureSettingsMixin, BaseSettings):
        model_config = {"env_prefix": "MYAPP_"}
        complex_config: dict = {}

    # Raises ValueError if MYAPP_COMPLEX_CONFIG exceeds 64KB

Error Handling
--------------

.. code-block:: python

    from buvis.pybase.configuration import (
        ConfigResolver,
        ConfigurationError,
        MissingEnvVarError,
    )
    from myapp.settings import PhotoSettings

    try:
        resolver = ConfigResolver()
        settings = resolver.resolve(PhotoSettings)
    except MissingEnvVarError as e:
        print(f"Missing required env vars: {e.var_names}")
    except ConfigurationError as e:
        print(f"Config error: {e}")

Testing
-------

Testing Code That Uses Settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For unit tests, create settings directly without the resolver:

.. code-block:: python

    import pytest
    from myapp.settings import MyAppSettings

    def test_with_custom_settings():
        # Create settings with test values directly
        settings = MyAppSettings(
            debug=True,
            db={"host": "test-db", "port": 5433},
        )
        assert settings.debug is True
        assert settings.db.host == "test-db"

Mocking get_settings in Click Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``pytest-mock`` to mock ``get_settings`` in CLI tests:

.. code-block:: python

    import pytest
    from click.testing import CliRunner
    from myapp.cli import main
    from myapp.settings import MyAppSettings

    @pytest.fixture
    def mock_settings(mocker):
        settings = MyAppSettings(debug=True)
        mocker.patch("myapp.cli.get_settings", return_value=settings)
        return settings

    def test_cli_with_mocked_settings(mock_settings):
        runner = CliRunner()
        result = runner.invoke(main)
        assert result.exit_code == 0

Testing with Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``monkeypatch`` to set env vars for integration tests:

.. code-block:: python

    def test_settings_from_env(monkeypatch):
        monkeypatch.setenv("BUVIS_MYAPP_DEBUG", "true")
        monkeypatch.setenv("BUVIS_MYAPP__DB__HOST", "env-db")

        from buvis.pybase.configuration import ConfigResolver
        from myapp.settings import MyAppSettings

        resolver = ConfigResolver()
        settings = resolver.resolve(MyAppSettings)

        assert settings.debug is True
        assert settings.db.host == "env-db"

Troubleshooting
---------------

Missing Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If YAML uses ``${VAR}`` without a default, you'll get ``MissingEnvVarError``:

.. code-block:: yaml

    # buvis.yaml
    database:
      password: ${DB_PASSWORD}  # Fails if not set

    # Fix: provide default
    database:
      password: ${DB_PASSWORD:-}  # Empty string default

YAML Not Loading
~~~~~~~~~~~~~~~~

Check file locations (in order):

1. ``$BUVIS_CONFIG_DIR/buvis.yaml``
2. ``~/.config/buvis/buvis.yaml``
3. ``~/.buvis/buvis.yaml``
4. ``./buvis.yaml``

Debug with:

.. code-block:: python

    from buvis.pybase.configuration import ConfigResolver

    resolver = ConfigResolver()
    settings = resolver.resolve(MySettings)
    print(resolver.sources)  # Shows where each value came from

Precedence Confusion
~~~~~~~~~~~~~~~~~~~~

CLI always wins, then ENV, then YAML, then defaults.

.. code-block:: bash

    # This won't work as expected:
    export BUVIS_DEBUG=true
    myapp --no-debug  # CLI wins -> debug=False

--------------

API Reference
=============

Core Classes
------------

GlobalSettings
~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.configuration.GlobalSettings
   :members:
   :undoc-members:
   :show-inheritance:

ToolSettings
~~~~~~~~~~~~

.. autoclass:: buvis.pybase.configuration.ToolSettings
   :members:
   :undoc-members:
   :show-inheritance:

ConfigResolver
~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.configuration.ConfigResolver
   :members:
   :undoc-members:
   :show-inheritance:

ConfigSource
~~~~~~~~~~~~

.. autoclass:: buvis.pybase.configuration.ConfigSource
   :members:
   :undoc-members:
   :show-inheritance:

Mixins
------

SafeLoggingMixin
~~~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.configuration.SafeLoggingMixin
   :members:
   :undoc-members:
   :show-inheritance:

SecureSettingsMixin
~~~~~~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.configuration.SecureSettingsMixin
   :members:
   :undoc-members:
   :show-inheritance:

Click Integration
-----------------

.. autofunction:: buvis.pybase.configuration.buvis_options

.. autofunction:: buvis.pybase.configuration.get_settings

Exceptions
----------

.. autoexception:: buvis.pybase.configuration.ConfigurationError
   :members:
   :show-inheritance:

.. autoexception:: buvis.pybase.configuration.ConfigurationKeyNotFoundError
   :members:
   :show-inheritance:

.. autoexception:: buvis.pybase.configuration.MissingEnvVarError
   :members:
   :show-inheritance:

Validators
----------

.. autofunction:: buvis.pybase.configuration.validate_nesting_depth

.. autofunction:: buvis.pybase.configuration.validate_json_env_size

.. autofunction:: buvis.pybase.configuration.get_model_depth

.. autofunction:: buvis.pybase.configuration.is_sensitive_field

Constants
---------

.. autodata:: buvis.pybase.configuration.MAX_NESTING_DEPTH

.. autodata:: buvis.pybase.configuration.MAX_JSON_ENV_SIZE
