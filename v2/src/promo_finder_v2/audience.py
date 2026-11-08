"""Simulated audience: two blind viewers react to each clip line by line; code turns that into an engagement score.

Clips are shuffled (seeded) so versions of one moment don't sit together, and sent 8 per call with no title, show
context or editor notes. A clip whose reply is missing or invalid is retried once in a smaller call; if it fails
again it stays unscored rather than guessed."""
from __future__ import annotations

import logging
import random
from typing import Callable

from . import engagement, prompts
from .budget import BudgetExceeded
from .finder import batches
from .llm import LLM, LLMError
from .models import ClipReaction, Engagement, Episode, Promo, RawAudience
from .transcript import ClipLine, clip_lines, render_clip

log = logging.getLogger(__name__)
CLIPS_PER_CALL = 8

Scores = dict[str, tuple[ClipReaction, Engagement]]  # promo_id -> reaction and engagement


def check_reaction(raw: dict, lines: list[ClipLine]) -> ClipReaction:
    """Validate one clip's reply against its own lines; beats come back in clip order."""
    reaction = ClipReaction.model_validate(raw)
    expected = [line.line for line in lines]
    got = [beat[0] for beat in reaction.beats]
    if sorted(got) != sorted(expected):
        missing = sorted(set(expected) - set(got))
        extra = sorted({line for line in got if got.count(line) > 1 or line not in expected})
        raise ValueError(f"beats must cover {expected[0]}-{expected[-1]} once each "
                         f"(missing {missing or 'none'}, duplicate or unknown {extra or 'none'})")
    order = {line: i for i, line in enumerate(expected)}
    return reaction.model_copy(update={"beats": sorted(reaction.beats, key=lambda beat: order[beat[0]])})


def score_clips(promos: list[Promo], episodes: dict[int, Episode], llm: LLM, weight_a: float = 0.65,
                per_call: int = CLIPS_PER_CALL, seed: int = 0, tag: str = "audience") -> tuple[Scores, list[str]]:
    """Scores clips without changing the promos (the reliability check re-scores the same clips).
    Returns (scores by promo_id, tags of calls that failed)."""
    order = list(promos)
    random.Random(seed).shuffle(order)
    scores: Scores = {}
    failed: list[str] = []
    judge_in_batches(order, per_call, tag, lambda group, name, retry:
                     _score_group(group, episodes, llm, weight_a, name, scores, failed, retry))
    return scores, failed


def judge_in_batches(items: list, per_call: int, tag: str, judge_group: Callable[[list, str, bool], list]) -> None:
    """Calls judge_group(group, call tag, retry) per batch. Whatever a batch leaves unjudged is retried once, together
    in one smaller call; if it fails again it stays unjudged rather than guessed."""
    for i, group in enumerate(batches(items, per_call), 1):
        name = f"{tag}-{i:02d}"
        missed = judge_group(group, name, False)
        if missed:
            log.warning("%s: %d items incomplete, retrying them once", name, len(missed))
            judge_group(missed, f"{name}-retry", True)


def apply(promos: list[Promo], scores: Scores) -> None:
    for p in promos:
        if p.promo_id in scores:
            p.reaction, p.engagement = scores[p.promo_id]


def _score_group(group: list[Promo], episodes: dict[int, Episode], llm: LLM, weight_a: float, tag: str,
                 scores: Scores, failed: list[str], retry: bool) -> list[Promo]:
    """Scores one call's clips into `scores`; returns the promos whose reply was missing or invalid."""
    clips = {f"C{j:02d}": (p, clip_lines(p, episodes)) for j, p in enumerate(group, 1)}
    user = prompts.audience_user([(clip_id, render_clip(lines)) for clip_id, (_, lines) in clips.items()], retry)
    try:
        result = llm.complete_json(prompts.AUDIENCE_SYSTEM, user, RawAudience, tag=tag)
    except (LLMError, BudgetExceeded) as err:
        log.error("%s failed: %s", tag, err)
        failed.append(tag)
        return []
    for raw in result.clips:
        clip_id = raw.get("clip")
        if clip_id not in clips:
            continue
        promo, lines = clips[clip_id]
        try:
            reaction = check_reaction(raw, lines)
        except ValueError as err:  # pydantic's ValidationError is a ValueError
            log.warning("%s %s: %s", tag, clip_id, str(err)[:200])
            continue
        scores[promo.promo_id] = (reaction, engagement.score(lines, reaction, weight_a))
    return [p for p, _ in clips.values() if p.promo_id not in scores]
