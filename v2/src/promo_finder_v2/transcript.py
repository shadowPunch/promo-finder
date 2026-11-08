"""Block ids and text rendering, shared by prompts (finder, judge) and reports."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Block, Episode, Promo
from .timecode import format_tc

_REF = re.compile(r"^E(\d+)L(\d+)$")
_LABELS = {"camera": "CAMERA", "action": "ACTION", "sfx": "SOUND FX"}


def ref(episode: int, line_id: int) -> str:
    return f"E{episode:02d}L{line_id:03d}"


def parse_ref(text: str) -> tuple[int, int]:
    match = _REF.match(text.strip().upper())
    if not match:
        raise ValueError(f"bad block id: {text!r}")
    return int(match.group(1)), int(match.group(2))


def _label(b: Block) -> str:
    if b.kind == "dialogue":
        return f"{b.speaker} {b.tone}" if b.tone else b.speaker
    return _LABELS[b.kind]


def render_block(episode: int, b: Block) -> str:
    return f"{ref(episode, b.line_id)} [{format_tc(b.start)}-{format_tc(b.end)}] {_label(b)}: {b.text}"


def render_episode(ep: Episode) -> str:
    header = f"=== EPISODE {ep.number} (duration {format_tc(ep.duration)}) ==="
    return "\n".join([header, *(render_block(ep.number, b) for b in ep.blocks)])


def blocks_between(ep: Episode, start: float, end: float) -> list[Block]:
    """Blocks that begin inside [start, end)."""
    return [b for b in ep.blocks if start <= b.start < end]


def render_promo(promo: Promo, episodes: dict[int, Episode]) -> str:
    """The promo as a viewer meets it: times from the clip start, no ids, cuts marked."""
    lines: list[str] = []
    offset = 0.0
    for i, seg in enumerate(promo.segments):
        if i:
            lines.append("--- CUT ---")
        for b in blocks_between(episodes[seg.episode], seg.start, seg.end):
            lines.append(f"+{offset + b.start - seg.start:04.1f}s {_label(b)}: {b.text}")
        offset += seg.duration
    return "\n".join(lines)


@dataclass(frozen=True)
class ClipLine:
    """One block as a viewer meets it: numbered, with times from the clip start."""
    line: str          # "L01"
    start: float
    end: float
    text: str          # "SPEAKER (Tone): words"
    cut_before: bool   # first line after a cut


def clip_lines(promo: Promo, episodes: dict[int, Episode]) -> list[ClipLine]:
    lines: list[ClipLine] = []
    offset = 0.0
    for i, seg in enumerate(promo.segments):
        for j, b in enumerate(blocks_between(episodes[seg.episode], seg.start, seg.end)):
            lines.append(ClipLine(
                line=f"L{len(lines) + 1:02d}",
                start=round(offset + b.start - seg.start, 2),
                end=round(offset + min(b.end, seg.end) - seg.start, 2),
                text=f"{_label(b)}: {b.text}",
                cut_before=i > 0 and j == 0,
            ))
        offset += seg.duration
    return lines


def render_clip(lines: list[ClipLine]) -> str:
    out: list[str] = []
    for line in lines:
        if line.cut_before:
            out.append("--- CUT ---")
        out.append(f"{line.line} [+{line.start:04.1f}-{line.end:04.1f}] {line.text}")
    return "\n".join(out)
