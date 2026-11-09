from __future__ import annotations

from typing import Any

from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

EXCALIDRAW_DRAWING = """%%
# Drawing
```json
{
\t"type": "excalidraw",
\t"version": 2,
\t"source": "https://github.com/zsviczian/obsidian-excalidraw-plugin/releases/tag/2.1.7",
\t"elements": [],
\t"appState": {
\t\t"theme": "light",
\t\t"viewBackgroundColor": "#ffffff",
\t\t"currentItemStrokeColor": "#1e1e1e",
\t\t"currentItemBackgroundColor": "transparent",
\t\t"currentItemFillStyle": "solid",
\t\t"currentItemStrokeWidth": 2,
\t\t"currentItemStrokeStyle": "solid",
\t\t"currentItemRoughness": 1,
\t\t"currentItemOpacity": 100,
\t\t"currentItemFontFamily": 1,
\t\t"currentItemFontSize": 20,
\t\t"currentItemTextAlign": "left",
\t\t"currentItemStartArrowhead": null,
\t\t"currentItemEndArrowhead": "arrow",
\t\t"scrollX": 431,
\t\t"scrollY": 483.99609375,
\t\t"zoom": {
\t\t\t"value": 1
\t\t},
\t\t"currentItemRoundness": "round",
\t\t"gridSize": null,
\t\t"gridColor": {
\t\t\t"Bold": "#C9C9C9FF",
\t\t\t"Regular": "#EDEDEDFF"
\t\t},
\t\t"currentStrokeOptions": null,
\t\t"previousGridSize": null,
\t\t"frameRendering": {
\t\t\t"enabled": true,
\t\t\t"clip": true,
\t\t\t"name": true,
\t\t\t"outline": true
\t\t},
\t\t"objectsSnapModeEnabled": false
\t},
\t"files": {}
}
```
%%"""


class IllustratedNoteTemplate:
    """Excalidraw note; the vault's ``page.convert-to-illustrated-note.tpl``.

    ``{id}`` in the drawing link is filled by the ``set_illustration_link`` hook
    once the fixers have assigned the id.
    """

    name = "illustrated-note"

    def questions(self) -> list[Question]:
        return []

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        title = answers.get("title", "")
        data = ZettelData()
        data.metadata["type"] = "illustrated-note"
        data.metadata["title"] = title
        data.metadata["excalidraw-plugin"] = "parsed"
        data.metadata["excalidraw-open-md"] = True
        tags_raw = answers.get("tags", "")
        if tags_raw:
            data.metadata["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        data.sections = [
            (f"# {title}", f"![{title}]({{id}}.svg)"),
            ("# Text Elements", EXCALIDRAW_DRAWING),
        ]
        return data

    def hooks(self) -> list[Hook]:
        return [Hook(name="set_illustration_link")]
