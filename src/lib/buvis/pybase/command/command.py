import warnings
from pathlib import Path
from typing import Any, cast

import yaml

from buvis.pybase.adapters.console.console import console
from buvis.pybase.configuration.exceptions import ConfigurationKeyNotFoundError

FILENAME_COMMAND_INPUT_SPECIFICATION = "command_input_spec.yaml"


class BuvisCommand:
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        warnings.warn(
            "BuvisCommand is deprecated and will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )

    def _setattr_from_config(
        self: "BuvisCommand",
        cfg: Any,
        child_module_path: str,
    ) -> None:
        input_spec_path = Path(child_module_path).parent.joinpath(
            FILENAME_COMMAND_INPUT_SPECIFICATION,
        )

        with input_spec_path.open("r") as input_spec_file:
            input_spec = yaml.safe_load(input_spec_file)
        input_spec_dict = cast(dict[str, Any], input_spec)

        for key, spec in input_spec_dict.items():
            try:
                self.__setattr__(key, cfg.get_configuration_item(key, spec["default"]))
            except ConfigurationKeyNotFoundError as _:
                if spec.get("panic"):
                    console.panic(key["panic"])  # type: ignore[index]
