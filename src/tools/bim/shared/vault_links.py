"""Vault cross-links for ``bim create``: contact mentions and the daily-note log entry.

Ported from the create-note skill's ``vault_links.py``. Pure text and file
helpers: no Click, no console.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from buvis.pybase.filesystem import atomic_write_text

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.S)
# Text that must never be rewritten: code, existing links, and bare URLs.
PROTECTED = re.compile(
    r"```.*?```|~~~.*?~~~|`[^`\n]*`|\[\[.*?\]\]|!?\[[^\]\n]*\]\([^)\n]*\)|<[a-z][a-z0-9+.-]*:[^>\s]*>|https?://\S+",
    re.S | re.I,
)
CONTACT_HEAD_BYTES = 2048


def daily_log_entry(now: datetime, wikilink: str) -> str:
    """Same shape as the QuickAdd capture: ``- [ ] _DD.MM.YYYY HH:mm:ss_ - entry``."""
    return f"- [ ] _{now:%d.%m.%Y %H:%M:%S}_ - {wikilink}"


def append_daily_log(path_daily: Path, now: datetime, wikilink: str) -> dict[str, str]:
    """Add a log entry for the new note to today's daily note. Never creates the daily note."""
    path = path_daily / f"{now:%Y-%m-%d}.md"
    entry = daily_log_entry(now, wikilink)
    if not path.is_file():
        return {"status": f"skipped: {path} does not exist (Obsidian creates it)", "entry": entry}
    lines = path.read_text(encoding="utf-8").split("\n")
    heading = next((n for n, line in enumerate(lines) if re.fullmatch(r"## Log[ \t]*", line)), None)
    if heading is None:
        return {"status": f"skipped: {path} has no '## Log' section", "entry": entry}
    end, fenced = len(lines), False
    for number in range(heading + 1, len(lines)):
        if lines[number].lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,2} ", lines[number]):
            end = number
            break
    insert_at = heading + 1
    for number in range(heading + 1, end):
        if lines[number].strip():
            insert_at = number + 1
    lines.insert(insert_at, entry)
    atomic_write_text(path, "\n".join(lines))
    return {"status": "added", "path": str(path), "entry": entry}


def _fold(text: str) -> tuple[str, list[int]]:
    """Lowercase and drop diacritics, keeping the source index of every folded character."""
    out: list[str] = []
    index: list[int] = []
    for position, char in enumerate(text):
        for part in unicodedata.normalize("NFKD", char):
            if not unicodedata.combining(part):
                out.append(part.lower())
                index.append(position)
    return "".join(out), index


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def _frontmatter_names(frontmatter: str) -> tuple[str, list[str]]:
    title, aliases = "", []
    lines = frontmatter.split("\n")
    for number, line in enumerate(lines):
        key, _, value = line.partition(":")
        if key == "title":
            title = _unquote(value)
        elif key == "aliases":
            value = value.strip()
            if value.startswith("["):
                aliases = [_unquote(item) for item in value.strip("[]").split(",")]
            elif value:
                aliases = [_unquote(item) for item in value.split(",")]
            else:
                for following in lines[number + 1 :]:
                    if not following.lstrip().startswith("- "):
                        break
                    aliases.append(_unquote(following.lstrip()[2:]))
    return title, [alias for alias in aliases if alias]


def contact_names(contact_dir: Path) -> dict[str, str]:
    """Map each unambiguous multi-word name (title, aliases, "Last, First") to its contact slug.

    Single-word names (first names, nicknames, company short names) are left out:
    they match too many other people and words to link without a human decision.
    """
    owners: dict[str, set[str]] = {}
    for path in sorted(contact_dir.glob("*.md")):
        try:
            with path.open(encoding="utf-8") as handle:
                head = handle.read(CONTACT_HEAD_BYTES)
        except (OSError, UnicodeDecodeError):
            continue
        match = FRONTMATTER.match(head.replace("\r\n", "\n"))
        if not match:
            continue
        title, aliases = _frontmatter_names(match.group(1))
        names = [title, *aliases]
        words = title.split()
        if len(words) == 2:
            names.append(f"{words[1]}, {words[0]}")
        for name in names:
            if len(name.split()) >= 2:
                owners.setdefault(_fold(" ".join(name.split()))[0], set()).add(path.stem)
    return {name: next(iter(slugs)) for name, slugs in owners.items() if len(slugs) == 1}


def link_contacts(text: str, names: dict[str, str], link_prefix: str, skip_slug: str = "") -> tuple[str, list[str]]:
    """Wikilink the first mention of each known contact; return the new text and the wikilinks added."""
    if not names or not text:
        return text, []
    folded, index = _fold(text)
    protected = [(m.start(), m.end()) for m in PROTECTED.finditer(text)]
    candidates: list[tuple[int, int, str]] = []
    for name, slug in names.items():
        if slug == skip_slug:
            continue
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in name.split()) + r"(?!\w)"
        for match in re.finditer(pattern, folded):
            start, end = index[match.start()], index[match.end() - 1] + 1
            if not any(start < p_end and p_start < end for p_start, p_end in protected):
                candidates.append((start, end, slug))
    candidates.sort(key=lambda c: (c[0], c[0] - c[1]))
    chosen: list[tuple[int, int, str]] = []
    for start, end, slug in candidates:
        if chosen and start < chosen[-1][1]:
            continue
        if any(slug == picked[2] for picked in chosen):
            continue
        chosen.append((start, end, slug))
    links = []
    for start, end, slug in reversed(chosen):
        link = f"[[{link_prefix}/{slug}|{text[start:end]}]]"
        text = text[:start] + link + text[end:]
        links.append(link)
    return text, links[::-1]


__all__ = ["append_daily_log", "contact_names", "daily_log_entry", "link_contacts"]
