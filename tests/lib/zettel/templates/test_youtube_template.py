from __future__ import annotations

import re

import pytest
from buvis.pybase.zettel.domain.templates.youtube import YoutubeTemplate, extract_video_id

VIDEO_ID = "dQw4w9WgXcQ"


class TestExtractVideoId:
    @pytest.mark.parametrize(
        "value",
        [
            VIDEO_ID,
            f"  {VIDEO_ID} ",
            f"https://youtu.be/{VIDEO_ID}?t=1",
            f"https://www.youtube.com/watch?v={VIDEO_ID}&list=PL1",
            f"youtube.com/shorts/{VIDEO_ID}",
            f"https://m.youtube.com/live/{VIDEO_ID}",
            f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
            f"https://www.youtube.com/v/{VIDEO_ID}",
        ],
    )
    def test_accepts_known_url_shapes(self, value: str) -> None:
        assert extract_video_id(value) == VIDEO_ID

    @pytest.mark.parametrize(
        "value",
        [
            f"https://example.com/watch?v={VIDEO_ID}",
            f"https://evilyoutube.com/watch?v={VIDEO_ID}",
            f"https://www.youtube.com/channel/{VIDEO_ID}",
            "https://www.youtube.com/watch?v=short",
            "short",
            "",
        ],
    )
    def test_rejects_anything_else(self, value: str) -> None:
        with pytest.raises(ValueError, match=re.escape(f"cannot find a YouTube video id in '{value.strip()}'")):
            extract_video_id(value)


class TestYoutubeTemplate:
    def test_name_question_and_body_section(self) -> None:
        t = YoutubeTemplate()
        assert t.name == "youtube"
        assert t.body_section == "## Notes"
        assert [(q.key, q.required) for q in t.questions()] == [("video", True)]
        assert t.hooks() == []

    def test_build_data_is_a_note_pointing_at_the_video(self) -> None:
        data = YoutubeTemplate().build_data({"title": "Talk", "video": f"https://youtu.be/{VIDEO_ID}", "tags": "video"})

        assert data.metadata["type"] == "note"
        assert data.metadata["title"] == "Talk"
        assert data.metadata["summary"] == "One sentence summarizing the content"
        assert data.metadata["origin"] == "youtube"
        assert data.metadata["author"] == ""
        assert data.metadata["source"] == f"https://www.youtube.com/watch?v={VIDEO_ID}"
        assert data.metadata["tags"] == ["video"]
        heading, body = data.sections[0]
        assert heading == "# Talk"
        assert body.startswith(
            f'<iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/{VIDEO_ID}"'
        )
        assert body.endswith("</iframe>\n\n> [!abstract] Summary\n> One paragraph summarizing the content.")
        assert data.sections[1] == ("## Notes", "")

    def test_invalid_video_fails_build(self) -> None:
        with pytest.raises(ValueError, match="cannot find a YouTube video id"):
            YoutubeTemplate().build_data({"title": "Talk", "video": "nope"})
