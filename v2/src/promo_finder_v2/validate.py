"""Turn LLM candidates into exact, rule-checked promo segments, or a rejection with a reason code.

The LLM only points at blocks; every time, length and boundary rule is enforced here, in code."""
from __future__ import annotations

import hashlib

from .models import Block, Candidate, Episode, Promo, Rejection, Segment
from .transcript import parse_ref

MIN_S, MAX_S = 20.0, 60.0
HOOK_WINDOW_S = 3.0  # the hook must start within this many seconds of the promo start
CLIFF_TAIL_S = 2.0   # at most this much may play after the cliffhanger block ends


class Invalid(ValueError):
    """Carries a reason like 'too_short (12.0s)'."""


def validate(candidate: Candidate, episodes: dict[int, Episode]) -> Promo | Rejection:
    try:
        segments, fixes = _resolve(candidate, episodes)
    except Invalid as err:
        return Rejection(raw=candidate.model_dump(), reason=str(err))
    return Promo(promo_id=_promo_id(segments), candidate=candidate, segments=segments, fixes=fixes)


def _lookup(ref: str, episodes: dict[int, Episode]) -> tuple[int, Block]:
    try:
        ep_no, line_id = parse_ref(ref)
    except ValueError:
        raise Invalid(f"bad_ref ({ref})") from None
    episode = episodes.get(ep_no)
    block = episode.block(line_id) if episode else None
    if block is None:
        raise Invalid(f"bad_ref ({ref})")
    return ep_no, block


def _resolve(c: Candidate, episodes: dict[int, Episode]) -> tuple[list[Segment], list[str]]:
    fixes: list[str] = []
    segs: list[list] = []  # [episode, start, end], mutable while repairing
    for s in c.segments:
        ep_a, first = _lookup(s.start, episodes)
        ep_b, last = _lookup(s.end, episodes)
        if ep_a != ep_b:
            raise Invalid(f"segment_spans_episodes ({s.start}-{s.end})")
        if last.end <= first.start:
            raise Invalid(f"segment_reversed ({s.start}-{s.end})")
        segs.append([ep_a, first.start, last.end])

    ep_h, hook = _lookup(c.hook_ref, episodes)
    head = segs[0]
    if ep_h != head[0] or not head[1] <= hook.start < head[2]:
        raise Invalid(f"hook_outside_first_segment ({c.hook_ref})")
    if hook.start - head[1] > HOOK_WINDOW_S:
        head[1] = hook.start
        fixes.append("start_moved_to_hook")

    ep_c, cliff = _lookup(c.cliffhanger_ref, episodes)
    tail = segs[-1]
    if ep_c != tail[0] or not tail[1] <= cliff.start < tail[2]:
        raise Invalid(f"cliffhanger_outside_last_segment ({c.cliffhanger_ref})")
    if tail[2] - cliff.end > CLIFF_TAIL_S:
        tail[2] = cliff.end
        fixes.append("end_trimmed_to_cliffhanger")
    elif cliff.end > tail[2]:
        tail[2] = cliff.end
        fixes.append("end_extended_to_cliffhanger")

    for s in segs:
        snapped = _snap_to_dialogue(episodes[s[0]], s[1], s[2])
        if snapped != (s[1], s[2]):
            s[1], s[2] = snapped
            fixes.append("snapped_to_dialogue")

    if hook.start - head[1] > HOOK_WINDOW_S:
        raise Invalid("hook_too_late_after_snapping")
    for i, a in enumerate(segs):
        for b in segs[i + 1:]:
            if a[0] == b[0] and a[1] < b[2] and b[1] < a[2]:
                raise Invalid("overlapping_segments")
    total = sum(end - start for _, start, end in segs)
    if total < MIN_S:
        raise Invalid(f"too_short ({total:.1f}s)")
    if total > MAX_S:
        raise Invalid(f"too_long ({total:.1f}s)")
    return [Segment(ep, start, end) for ep, start, end in segs], fixes


def _snap_to_dialogue(ep: Episode, start: float, end: float) -> tuple[float, float]:
    """Widen [start, end] so no line of dialogue is cut mid-sentence."""
    for b in ep.blocks:
        if b.kind != "dialogue":
            continue
        if b.start < start < b.end:
            start = b.start
        if b.start < end < b.end:
            end = b.end
    return start, end


def _promo_id(segments: list[Segment]) -> str:
    key = "|".join(f"{s.episode}:{s.start:.2f}-{s.end:.2f}" for s in segments)
    return hashlib.sha1(key.encode()).hexdigest()[:8]
