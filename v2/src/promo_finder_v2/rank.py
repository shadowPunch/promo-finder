"""Score, de-duplicate and rank validated promos, with a cold-viewer judge pass on the shortlist."""
from __future__ import annotations

import logging
import random

from . import prompts
from .llm import LLM, LLMError
from .models import Episode, JudgeResult, Promo
from .transcript import render_promo

log = logging.getLogger(__name__)

# The hook weighs most: a promo that doesn't stop the scroll is never watched.
WEIGHTS = {"hook": 0.4, "cliffhanger": 0.3, "standalone": 0.3}
SPOILER_PENALTY = {"low": 0.0, "medium": 0.25, "high": 0.75}
# Assumption: ads should land new viewers at the start of the show (free episodes, least backstory).
EARLY_EPISODE_MAX = 10
EARLY_BONUS = 0.25
DUPLICATE_OVERLAP = 0.5  # promos sharing more than half of the shorter one's footage are duplicates


def rule_score(p: Promo) -> float:
    c = p.candidate
    score = (WEIGHTS["hook"] * c.hook_score
             + WEIGHTS["cliffhanger"] * c.cliffhanger_score
             + WEIGHTS["standalone"] * c.standalone_score
             - SPOILER_PENALTY[c.spoiler_risk])
    if p.segments[0].episode <= EARLY_EPISODE_MAX:
        score += EARLY_BONUS
    return round(score, 3)


def shared_seconds(a: Promo, b: Promo) -> float:
    return sum(
        max(0.0, min(x.end, y.end) - max(x.start, y.start))
        for x in a.segments for y in b.segments if x.episode == y.episode
    )


def dedupe(promos: list[Promo]) -> list[Promo]:
    """Keep the best-scoring promo of each group that shares most of its footage."""
    kept: list[Promo] = []
    for p in sorted(promos, key=lambda p: p.rule_score, reverse=True):
        if all(shared_seconds(p, k) <= DUPLICATE_OVERLAP * min(p.duration, k.duration) for k in kept):
            kept.append(p)
    return kept


def judge(promos: list[Promo], episodes: dict[int, Episode], llm: LLM, top_k: int = 15, seed: int = 0) -> None:
    """The judge sees only the clip text, with no show context, in shuffled order."""
    shortlist = sorted(promos, key=lambda p: p.rule_score, reverse=True)[:top_k]
    if not shortlist:
        return
    random.Random(seed).shuffle(shortlist)  # reduce position bias
    by_id = {f"C{i:02d}": p for i, p in enumerate(shortlist, 1)}
    user = prompts.judge_user([(clip_id, render_promo(p, episodes)) for clip_id, p in by_id.items()])
    try:
        result = llm.complete_json(prompts.JUDGE_SYSTEM, user, JudgeResult, tag="judge")
    except LLMError as err:
        log.error("judge failed, ranking by rule score only: %s", err)
        return
    for verdict in result.verdicts:
        if verdict.clip in by_id:
            by_id[verdict.clip].verdict = verdict


def rank(promos: list[Promo]) -> list[Promo]:
    """Judged promos first, then by final score (rule score + judge overall)."""
    ranked = sorted(promos, key=lambda p: (p.verdict is not None, p.final_score, p.rule_score), reverse=True)
    for i, p in enumerate(ranked, 1):
        p.rank = i
    return ranked
