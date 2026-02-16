from __future__ import annotations

from pathlib import Path
from typing import Literal

import click
from click.testing import CliRunner
from pydantic import BaseModel, Field

from buvis.pybase.configuration.generators import (
    apply_generated_options,
    generate_click_options,
)


class BoolModel(BaseModel):
    flag: bool = Field(False, description="A boolean flag")


class BoolOptionalModel(BaseModel):
    processed: bool | None = Field(None, description="Tri-state flag")


class PathModel(BaseModel):
    output: Path | None = Field(
        None,
        description="Output path",
        json_schema_extra={
            "path_file_okay": True,
            "path_dir_okay": False,
            "path_resolve": True,
        },
    )


class IntModel(BaseModel):
    count: int = Field(0, description="A count")


class LiteralModel(BaseModel):
    mode: Literal["fast", "slow"] = Field("fast", description="Processing mode")


class StringModel(BaseModel):
    name: str | None = Field(None, description="A name")


class PathsSkippedModel(BaseModel):
    paths: list[Path] = Field(..., description="Should be skipped")
    flag: bool = Field(False, description="Not skipped")


class CliHintsModel(BaseModel):
    query_file: str | None = Field(
        None,
        description="Query file",
        json_schema_extra={
            "cli_short": "-f",
            "cli_long": "--file",
            "cli_param": "query_file",
        },
    )


class MixedModel(BaseModel):
    paths: list[Path] = Field(...)
    highlight: bool = Field(False, description="Highlight output")
    output: Path | None = Field(None, description="Output path")


class TestGenerateClickOptions:
    def test_bool_field_generates_flag(self):
        opts = generate_click_options(BoolModel)
        assert len(opts) == 1

    def test_bool_optional_generates_flag_noflag(self):
        opts = generate_click_options(BoolOptionalModel)
        assert len(opts) == 1

    def test_path_field_generates_path_option(self):
        opts = generate_click_options(PathModel)
        assert len(opts) == 1

    def test_int_field_generates_int_option(self):
        opts = generate_click_options(IntModel)
        assert len(opts) == 1

    def test_literal_field_generates_choice(self):
        opts = generate_click_options(LiteralModel)
        assert len(opts) == 1

    def test_string_field_generates_option(self):
        opts = generate_click_options(StringModel)
        assert len(opts) == 1

    def test_paths_field_is_skipped(self):
        opts = generate_click_options(PathsSkippedModel)
        assert len(opts) == 1  # only flag, not paths

    def test_cli_hints_respected(self):
        opts = generate_click_options(CliHintsModel)
        assert len(opts) == 1

    def test_mixed_model_skips_paths(self):
        opts = generate_click_options(MixedModel)
        assert len(opts) == 2  # highlight + output, not paths


class TestApplyGeneratedOptions:
    def test_decorator_applies_options(self):
        @click.command()
        @apply_generated_options(BoolModel)
        def cmd(flag):
            click.echo(f"flag={flag}")

        result = CliRunner().invoke(cmd, ["--flag"])
        assert result.exit_code == 0
        assert "flag=True" in result.output

    def test_bool_optional_tristate(self):
        @click.command()
        @apply_generated_options(BoolOptionalModel)
        def cmd(processed):
            click.echo(f"processed={processed}")

        # No flag -> None
        result = CliRunner().invoke(cmd, [])
        assert "processed=None" in result.output

        # --processed -> True
        result = CliRunner().invoke(cmd, ["--processed"])
        assert "processed=True" in result.output

        # --no-processed -> False
        result = CliRunner().invoke(cmd, ["--no-processed"])
        assert "processed=False" in result.output

    def test_path_option(self):
        @click.command()
        @apply_generated_options(PathModel)
        def cmd(output):
            click.echo(f"type={type(output).__name__}")

        result = CliRunner().invoke(cmd, ["--output", "/tmp/test.txt"])
        assert result.exit_code == 0

    def test_int_option(self):
        @click.command()
        @apply_generated_options(IntModel)
        def cmd(count):
            click.echo(f"count={count}")

        result = CliRunner().invoke(cmd, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

    def test_literal_choice(self):
        @click.command()
        @apply_generated_options(LiteralModel)
        def cmd(mode):
            click.echo(f"mode={mode}")

        result = CliRunner().invoke(cmd, ["--mode", "slow"])
        assert result.exit_code == 0
        assert "mode=slow" in result.output

    def test_cli_hints_short_option(self):
        @click.command()
        @apply_generated_options(CliHintsModel)
        def cmd(query_file):
            click.echo(f"qf={query_file}")

        result = CliRunner().invoke(cmd, ["-f", "test.yml"])
        assert result.exit_code == 0
        assert "qf=test.yml" in result.output
