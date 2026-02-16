from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolManifest:
    name: str
    display_name: str
    module_name: str
    description: str
    category: str
    interfaces: dict[str, bool] = field(default_factory=dict)
    commands: dict[str, str] = field(default_factory=dict)
    requirements: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_toml(cls, path: Path) -> ToolManifest:
        import tomllib

        with open(path, "rb") as f:
            data = tomllib.load(f)
        tool = data["tool"]
        return cls(
            name=tool["name"],
            display_name=tool["display_name"],
            module_name=tool["module_name"],
            description=tool["description"],
            category=tool.get("category", ""),
            interfaces=tool.get("interfaces", {}),
            commands=tool.get("commands", {}),
            requirements=tool.get("requirements", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_tools_dev(tools_dir: Path) -> list[ToolManifest]:
    """Dev-time discovery: scan tools_dir for manifest.toml files."""
    manifests = []
    for manifest_path in sorted(tools_dir.glob("*/manifest.toml")):
        manifests.append(ToolManifest.from_toml(manifest_path))
    return manifests


def discover_tools_installed(package_names: list[str]) -> list[ToolManifest]:
    """Runtime discovery: read manifests from installed packages via importlib.resources."""
    import importlib.resources

    manifests = []
    for pkg in package_names:
        try:
            ref = importlib.resources.files(pkg) / "manifest.toml"
            with importlib.resources.as_file(ref) as path:
                manifests.append(ToolManifest.from_toml(path))
        except (ModuleNotFoundError, FileNotFoundError):
            continue
    return manifests
