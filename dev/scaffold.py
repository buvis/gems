"""Scaffold a new buvis-gems tool skeleton."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def _to_snake(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", name.lower()).strip("_")


def _to_pascal(name: str) -> str:
    return "".join(word.capitalize() for word in _to_snake(name).split("_"))


def _to_kebab(name: str) -> str:
    return _to_snake(name).replace("_", "-")


INIT_TEMPLATE = '''\
__version__ = "0.1.0"
__all__: list[str] = []
'''

MAIN_SIMPLE_TEMPLATE = '''\
from {snake}.cli import cli

cli()
'''

MAIN_MULTI_TEMPLATE = '''\
from {snake}.adapters.cli import cli

cli()
'''

SETTINGS_TEMPLATE = '''\
from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class {pascal}Settings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="{env_prefix}",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )
'''

CLI_TEMPLATE = '''\
from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings

from {snake}.settings import {pascal}Settings


@click.group(help="{description}")
@buvis_options(settings_class={pascal}Settings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("example", help="Example command")
@click.argument("text")
@click.pass_context
def example(ctx: click.Context, text: str) -> None:
    from {snake}.commands.example import CommandExample
    from {snake}.params.example import ExampleParams

    params = ExampleParams(text=text)
    cmd = CommandExample(params=params)
    result = cmd.execute()
    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.print(result.output, mode="raw")
    else:
        console.failure(result.error)


if __name__ == "__main__":
    cli()
'''

PARAMS_TEMPLATE = '''\
from __future__ import annotations

from pydantic import BaseModel, Field


class ExampleParams(BaseModel):
    text: str = Field(..., description="Text to process")
'''

COMMAND_TEMPLATE = '''\
from __future__ import annotations

from buvis.pybase.result import CommandResult

from {snake}.params.example import ExampleParams


class CommandExample:
    def __init__(self, params: ExampleParams) -> None:
        self.params = params

    def execute(self) -> CommandResult:
        return CommandResult(
            success=True,
            output=f"Processed: {{self.params.text}}",
        )
'''

MANIFEST_TEMPLATE = '''\
[tool]
name = "{kebab}"
display_name = "{pascal}"
module_name = "{snake}"
description = "{description}"
category = ""

[tool.interfaces]
cli = true
rest = false
tui = false
web = false

[tool.commands]
example = "Example command"

[tool.requirements]
python = ">=3.11"
extras = []
'''

TEST_CLI_TEMPLATE = '''\
from click.testing import CliRunner

from {cli_import}.cli import cli


class TestCli:
    def test_help(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_example(self):
        result = CliRunner().invoke(cli, ["example", "hello"])
        assert result.exit_code == 0
        assert "hello" in result.output
'''

CONFTEST_TEMPLATE = '''\
from __future__ import annotations

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
'''

EMPTY = ""

SIMPLE_TEMPLATES = {
    "__init__.py": INIT_TEMPLATE,
    "__main__.py": MAIN_SIMPLE_TEMPLATE,
    "cli.py": CLI_TEMPLATE,
    "settings.py": SETTINGS_TEMPLATE,
    "manifest.toml": MANIFEST_TEMPLATE,
    "commands/__init__.py": EMPTY,
    "commands/example.py": COMMAND_TEMPLATE,
    "params/__init__.py": EMPTY,
    "params/example.py": PARAMS_TEMPLATE,
}

MULTI_INTERFACE_TEMPLATES = {
    "__init__.py": INIT_TEMPLATE,
    "__main__.py": MAIN_MULTI_TEMPLATE,
    "settings.py": SETTINGS_TEMPLATE,
    "manifest.toml": MANIFEST_TEMPLATE,
    "commands/__init__.py": EMPTY,
    "commands/example.py": COMMAND_TEMPLATE,
    "params/__init__.py": EMPTY,
    "params/example.py": PARAMS_TEMPLATE,
    "adapters/__init__.py": EMPTY,
    "adapters/cli.py": CLI_TEMPLATE,
}

TEST_TEMPLATES = {
    "__init__.py": EMPTY,
    "test_cli.py": TEST_CLI_TEMPLATE,
    "conftest.py": CONFTEST_TEMPLATE,
}


def scaffold(name: str, description: str, *, multi_interface: bool = False) -> None:
    snake = _to_snake(name)
    pascal = _to_pascal(name)
    kebab = _to_kebab(name)

    tool_dir = Path(f"src/tools/{snake}")
    test_dir = Path(f"tests/tools/{snake}")

    if tool_dir.exists():
        raise FileExistsError(f"{tool_dir} already exists")

    # For test imports: simple uses {snake}, multi uses {snake}.adapters
    cli_import = f"{snake}.adapters" if multi_interface else snake

    ctx = {
        "snake": snake,
        "pascal": pascal,
        "kebab": kebab,
        "description": description,
        "env_prefix": f"BUVIS_{snake.upper()}_",
        "cli_import": cli_import,
    }

    templates = MULTI_INTERFACE_TEMPLATES if multi_interface else SIMPLE_TEMPLATES
    for rel_path, template in templates.items():
        path = tool_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.format(**ctx) if template else "")

    for rel_path, template in TEST_TEMPLATES.items():
        path = test_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.format(**ctx) if template else "")

    print(f"Created tool skeleton: {tool_dir}")
    print(f"Created test skeleton: {test_dir}")
    print(f"\nNext steps:")
    print(f'  1. Add entry point to pyproject.toml: {kebab} = "{snake}.cli:cli"')
    print("  2. Edit commands/example.py or add new commands")
    print(f"  3. Run: uv run {kebab} --help")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a new buvis-gems tool")
    parser.add_argument("--name", required=True, help="Tool name (kebab-case or snake_case)")
    parser.add_argument("--description", required=True, help="Tool description")
    parser.add_argument("--multi-interface", action="store_true", help="Generate multi-interface layout")
    args = parser.parse_args()
    scaffold(args.name, args.description, multi_interface=args.multi_interface)


if __name__ == "__main__":
    main()
