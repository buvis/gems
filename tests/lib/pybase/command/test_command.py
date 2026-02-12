from __future__ import annotations

import warnings

import pytest
from buvis.pybase.command.command import (
    FILENAME_COMMAND_INPUT_SPECIFICATION,
    BuvisCommand,
)
from buvis.pybase.configuration.exceptions import ConfigurationKeyNotFoundError


class _PanicKey(str):
    """String subclass that supports panic metadata for the deprecated logic."""

    def __new__(cls, value: str, panic_value: str) -> _PanicKey:
        obj = str.__new__(cls, value)
        obj._panic_value = panic_value
        return obj

    def __getitem__(self, item: str) -> str:
        if item == "panic":
            return self._panic_value
        raise KeyError(item)


def _create_dummy_command_subclass() -> type[BuvisCommand]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)

        class DummyCommand(BuvisCommand):
            pass

    return DummyCommand


def test_init_subclass_warns() -> None:
    with pytest.warns(DeprecationWarning, match="deprecated"):

        class _Command(BuvisCommand):
            pass

        assert issubclass(_Command, BuvisCommand)


def test_setattr_from_config_sets_attributes(tmp_path, mocker) -> None:
    child_dir = tmp_path / "child"
    child_dir.mkdir()

    spec_file = child_dir / FILENAME_COMMAND_INPUT_SPECIFICATION
    spec_file.write_text(
        "source_dir:\n  default: /tmp/source\noutput_format:\n  default: json\n",
    )

    module_file = child_dir / "foo.py"
    module_file.write_text("module")

    cfg = mocker.Mock()
    cfg.get_configuration_item.side_effect = ["value-one", "value-two"]

    command = _create_dummy_command_subclass()()
    command._setattr_from_config(cfg, str(module_file))

    assert command.source_dir == "value-one"
    assert command.output_format == "value-two"
    assert cfg.get_configuration_item.call_args_list == [
        mocker.call("source_dir", "/tmp/source"),
        mocker.call("output_format", "json"),
    ]


def test_setattr_from_config_panics_on_missing_key_with_panic(
    tmp_path,
    mocker,
) -> None:
    panic_key = _PanicKey("panic_item", "panic message")
    spec_data = {panic_key: {"default": "fallback", "panic": True}}

    mocker.patch(
        "buvis.pybase.command.command.yaml.safe_load",
        return_value=spec_data,
    )
    panic = mocker.patch("buvis.pybase.command.command.console.panic")

    cfg = mocker.Mock()
    cfg.get_configuration_item.side_effect = ConfigurationKeyNotFoundError()

    child_dir = tmp_path / "child"
    child_dir.mkdir()

    spec_file = child_dir / FILENAME_COMMAND_INPUT_SPECIFICATION
    spec_file.write_text("")

    module_file = child_dir / "foo.py"
    module_file.write_text("")

    command = _create_dummy_command_subclass()()
    command._setattr_from_config(cfg, str(module_file))

    panic.assert_called_once_with("panic message")


def test_setattr_from_config_ignores_missing_key_without_panic(
    tmp_path,
    mocker,
) -> None:
    child_dir = tmp_path / "child"
    child_dir.mkdir()

    spec_file = child_dir / FILENAME_COMMAND_INPUT_SPECIFICATION
    spec_file.write_text(
        "normal_item:\n  default: fallback\n",
    )

    module_file = child_dir / "foo.py"
    module_file.write_text("")

    panic = mocker.patch("buvis.pybase.command.command.console.panic")
    cfg = mocker.Mock()
    cfg.get_configuration_item.side_effect = ConfigurationKeyNotFoundError()

    command = _create_dummy_command_subclass()()
    command._setattr_from_config(cfg, str(module_file))

    panic.assert_not_called()
