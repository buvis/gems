from __future__ import annotations

import json

from buvis.pybase.zettel.domain.templates.illustrated_note import IllustratedNoteTemplate


class TestIllustratedNoteTemplate:
    def test_name_and_hook(self) -> None:
        t = IllustratedNoteTemplate()
        assert t.name == "illustrated-note"
        assert t.questions() == []
        assert [hook.name for hook in t.hooks()] == ["set_illustration_link"]

    def test_build_data_is_an_excalidraw_note_with_id_placeholder(self) -> None:
        data = IllustratedNoteTemplate().build_data({"title": "Sketch", "tags": "draw"})

        assert data.metadata["type"] == "illustrated-note"
        assert data.metadata["title"] == "Sketch"
        assert data.metadata["excalidraw-plugin"] == "parsed"
        assert data.metadata["excalidraw-open-md"] is True
        assert data.metadata["tags"] == ["draw"]
        assert data.sections[0] == ("# Sketch", "![Sketch]({id}.svg)")
        heading, drawing = data.sections[1]
        assert heading == "# Text Elements"
        assert drawing.startswith("%%\n# Drawing\n```json\n")
        assert drawing.endswith("\n```\n%%")
        fenced = drawing.split("```json\n", 1)[1].rsplit("\n```", 1)[0]
        assert json.loads(fenced)["type"] == "excalidraw"
        assert json.loads(fenced)["elements"] == []
