"""Quick screen and shortlist: a cold-viewer pass over every valid promo, then the moments worth working on.

The screen is v1's cold-viewer judge, run on all promos in large batches (cheap per clip). The shortlist takes the
best-screened promos, at most one per episode and none sharing most of their footage, so the expensive stages work
on distinct moments."""
from __future__ import annotations

import logging
import random
from typing import Callable

from . import prompts
from .budget import BudgetExceeded
from .finder import batches
from .llm import LLM, LLMError
from .models import Episode, Promo, ScreenResult
from .transcript import render_promo

log = logging.getLogger(__name__)
SCREEN_BATCH = 30
# Assumption carried from v1: ads should land new viewers near the start of the show.
EARLY_EPISODE_MAX = 10
EARLY_BONUS = 0.25
DUPLICATE_OVERLAP = 0.5  # promos sharing more than half of the shorter one's footage count as the same moment


def screen(promos: list[Promo], episodes: dict[int, Episode], llm: LLM, batch_size: int = SCREEN_BATCH,
           seed: int = 0) -> list[str]:
    """Sets `verdict` on every promo the screen scored; returns tags of failed batches."""
    order = list(promos)
    random.Random(seed).shuffle(order)  # reduce position bias
    failed: list[str] = []
    for i, group in enumerate(batches(order, batch_size), 1):
        tag = f"screen-{i:02d}"
        by_id = {f"C{j:02d}": p for j, p in enumerate(group, 1)}
        user = prompts.screen_user([(clip_id, render_promo(p, episodes)) for clip_id, p in by_id.items()])
        try:
            result = llm.complete_json(prompts.SCREEN_SYSTEM, user, ScreenResult, tag=tag)
        except (LLMError, BudgetExceeded) as err:
            log.error("%s failed: %s", tag, err)
            failed.append(tag)
            continue
        for verdict in result.verdicts:
            if verdict.clip in by_id:
                by_id[verdict.clip].verdict = verdict
    return failed


def screen_score(p: Promo) -> float:
    score = float(p.verdict.overall) if p.verdict else 0.0
    return score + (EARLY_BONUS if p.segments[0].episode <= EARLY_EPISODE_MAX else 0.0)


def _tiebreak(p: Promo) -> int:
    return p.verdict.stops_scroll + p.verdict.needs_next if p.verdict else 0


def shared_seconds(a: Promo, b: Promo) -> float:
    return sum(
        max(0.0, min(x.end, y.end) - max(x.start, y.start))
        for x in a.segments for y in b.segments if x.episode == y.episode
    )


def overlaps(a: Promo, b: Promo) -> bool:
    return shared_seconds(a, b) > DUPLICATE_OVERLAP * min(a.duration, b.duration)


def dedupe(promos: list[Promo], key: Callable[[Promo], float]) -> list[Promo]:
    """Keeps the best promo (by `key`) of each group that shares most of its footage, best first."""
    kept: list[Promo] = []
    for p in sorted(promos, key=key, reverse=True):
        if not any(overlaps(p, k) for k in kept):
            kept.append(p)
    return kept


def shortlist(promos: list[Promo], k: int = 12) -> list[Promo]:
    """Best-screened first (ties: stops_scroll + needs_next); at most one per episode (by first segment);
    no footage-sharing duplicates."""
    picked: list[Promo] = []
    used: set[int] = set()
    for p in sorted(promos, key=lambda p: (screen_score(p), _tiebreak(p)), reverse=True):
        episode = p.segments[0].episode
        if episode in used or any(overlaps(p, q) for q in picked):
            continue
        picked.append(p)
        used.add(episode)
        if len(picked) == k:
            break
    return picked
