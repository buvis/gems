from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field


@dataclass
class PropertyDef:
    type: str = "text"  # text|number|date|bool|select|tags|link|path|markdown
    label: str | None = None
    options: list[str] = dc_field(default_factory=list)


BUILTIN_SCHEMA: dict[str, PropertyDef] = {
    "id": PropertyDef(type="number", label="ID"),
    "title": PropertyDef(type="text", label="Title"),
    "date": PropertyDef(type="date", label="Date"),
    "type": PropertyDef(type="select", label="Type", options=["note", "project"]),
    "tags": PropertyDef(type="tags", label="Tags"),
    "publish": PropertyDef(type="bool", label="Publish"),
    "processed": PropertyDef(type="bool", label="Processed"),
    "completed": PropertyDef(type="bool", label="Completed"),
    "dev-type": PropertyDef(
        type="select",
        label="Dev type",
        options=["feature", "bugfix", "spike", "maintenance"],
    ),
    "us": PropertyDef(type="link", label="User Story"),
    "parent": PropertyDef(type="link", label="Parent"),
    "ticket": PropertyDef(type="link", label="Ticket"),
    "file_path": PropertyDef(type="path", label="File"),
}
