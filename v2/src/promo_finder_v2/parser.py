"""Parse Kuku-style timestamped screenplay .txt files into Episodes.

Format (case of scene headers varies between files):
    **SPEAKER (Tone):**   or   **CAMERA:** / **ACTION:** / **SOUND FX:**
    Start: (mm:ss.cc) | End: (mm:ss.cc)
    one line of text
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .models import Block, Episode
from .timecode import parse_tc

log = logging.getLogger(__name__)

_META = re.compile(r"^(EPISODE NUMBER|EPISODE LOGLINE)\s*:\s*(.*)$", re.I)
_HEADER = re.compile(r"^\*\*\s*(.+?)\s*:?\s*\*\*\s*:?\s*$")
_TIMES = re.compile(r"Start:\s*\(([\d:.]+)\)\s*\|\s*End:\s*\(([\d:.]+)\)", re.I)
_STOP = re.compile(r"^(---|SCENE \d+$)", re.I)
_NON_DIALOGUE = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sfx", "SFX": "sfx", "SOUND": "sfx", "MUSIC": "sfx"}


def parse_episode(path: Path) -> Episode:
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    meta: dict[str, str] = {}
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        if meta_match := _META.match(lines[i]):
            meta[meta_match.group(1).upper()] = meta_match.group(2).strip()
        header = _HEADER.match(lines[i])
        times = _TIMES.search(lines[i + 1]) if header and i + 1 < len(lines) else None
        if not times:
            i += 1
            continue
        j, text = i + 2, []
        while j < len(lines) and lines[j] and not _HEADER.match(lines[j]) and not _STOP.match(lines[j]):
            text.append(lines[j])
            j += 1
        block = _make_block(len(blocks) + 1, header.group(1), times, " ".join(text))
        if block is None:
            log.warning("%s: unreadable timing near line %d, block skipped", path.name, i + 2)
        else:
            blocks.append(block)
        i = j
    if not blocks:
        raise ValueError("no timed blocks found")
    return Episode(
        number=_episode_number(meta, path),
        logline=meta.get("EPISODE LOGLINE", ""),
        blocks=blocks,
        source=path.name,
    )


def parse_show(folder: Path) -> list[Episode]:
    """Every screenplay under `folder` (recursively), sorted by episode number."""
    episodes = []
    for path in sorted(Path(folder).rglob("*.txt")):
        try:
            episodes.append(parse_episode(path))
        except ValueError as err:
            log.warning("%s skipped: %s", path.name, err)
    episodes.sort(key=lambda e: e.number)
    numbers = [e.number for e in episodes]
    if len(numbers) != len(set(numbers)):
        raise ValueError(f"duplicate episode numbers in {folder}")
    return episodes


def _make_block(line_id: int, head: str, times: re.Match, text: str) -> Block | None:
    try:
        start, end = parse_tc(times.group(1)), parse_tc(times.group(2))
    except ValueError:
        return None
    if end < start:
        return None
    name, _, rest = head.partition(" (")
    name = name.strip().upper()
    kind = _NON_DIALOGUE.get(name, "dialogue")
    is_line = kind == "dialogue"
    return Block(
        line_id=line_id,
        kind=kind,
        speaker=name if is_line else None,
        tone=f"({rest}" if is_line and rest else None,
        start=start,
        end=end,
        text=text,
    )


def _episode_number(meta: dict[str, str], path: Path) -> int:
    for text in (meta.get("EPISODE NUMBER", ""), path.stem):
        if match := re.search(r"\d+", text):
            return int(match.group())
    raise ValueError(f"{path.name}: no episode number")
