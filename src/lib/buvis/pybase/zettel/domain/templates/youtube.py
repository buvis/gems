from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
YOUTUBE_HOSTS = ("youtube.com", "youtube-nocookie.com")


def extract_video_id(value: str) -> str:
    """Return the 11-character id from a YouTube URL or a bare id.

    Accepts ``youtu.be/ID``, ``youtube.com/watch?v=ID`` and the ``/live/``,
    ``/shorts/``, ``/embed/`` and ``/v/`` paths on youtube.com, its subdomains
    and youtube-nocookie.com.

    Raises:
        ValueError: When no id can be found.
    """
    value = value.strip()
    if YOUTUBE_ID.fullmatch(value):
        return value
    url = urlparse(value if "://" in value else "https://" + value)
    host = (url.hostname or "").lower()
    candidate = ""
    if host == "youtu.be":
        candidate = url.path.strip("/").split("/")[0]
    elif host in YOUTUBE_HOSTS or host.endswith(tuple(f".{known}" for known in YOUTUBE_HOSTS)):
        parts = [part for part in url.path.split("/") if part]
        if parts == ["watch"]:
            candidate = parse_qs(url.query).get("v", [""])[0]
        elif len(parts) >= 2 and parts[0] in ("live", "shorts", "embed", "v"):
            candidate = parts[1]
    if not YOUTUBE_ID.fullmatch(candidate):
        raise ValueError(f"cannot find a YouTube video id in '{value}'")
    return candidate


class YoutubeTemplate:
    """Notes on a video; the vault's ``page.convert-to-notes-on-youtube-video.tpl``."""

    name = "youtube"
    body_section = "## Notes"

    def questions(self) -> list[Question]:
        return [Question(key="video", prompt="YouTube URL or video id", required=True)]

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        video_id = extract_video_id(str(answers.get("video", "")))
        title = answers.get("title", "")
        data = ZettelData()
        data.metadata["type"] = "note"
        data.metadata["title"] = title
        data.metadata["summary"] = "One sentence summarizing the content"
        data.metadata["origin"] = "youtube"
        data.metadata["author"] = ""
        data.metadata["source"] = f"https://www.youtube.com/watch?v={video_id}"
        tags_raw = answers.get("tags", "")
        if tags_raw:
            data.metadata["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        iframe = (
            f'<iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/{video_id}"'
            ' title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write;'
            ' encrypted-media; gyroscope; picture-in-picture; web-share"'
            ' referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>'
        )
        data.sections = [
            (f"# {title}", f"{iframe}\n\n> [!abstract] Summary\n> One paragraph summarizing the content."),
            ("## Notes", ""),
        ]
        return data

    def hooks(self) -> list[Hook]:
        return []
