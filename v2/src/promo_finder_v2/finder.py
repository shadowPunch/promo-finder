"""Ask the LLM for promo candidates, a few consecutive episodes per call.

Several episodes per call let one promo join moments from neighbouring episodes and keep the call count low
(10 for a 50-episode show at the default of 5). With the Codex backend each call carries ~17K tokens of fixed
overhead, so fewer calls directly saves budget."""
from __future__ import annotations

import logging
from typing import Callable

from pydantic import BaseModel, ValidationError

from . import prompts
from .budget import BudgetExceeded
from .llm import LLM, LLMError
from .models import Candidate, Episode, Promo, Rejection
from .transcript import render_episode

log = logging.getLogger(__name__)


class RawBatch(BaseModel):
    candidates: list[dict]  # each one is validated separately, so one bad candidate doesn't sink the batch


def batches(items: list, per_call: int) -> list[list]:
    return [items[i:i + per_call] for i in range(0, len(items), per_call)]


def series_context(episodes: list[Episode]) -> str:
    return "\n".join(f"E{e.number:02d}: {e.logline}" for e in episodes)


def find_candidates(
    episodes: list[Episode],
    llm: LLM,
    per_call: int = 5,
    per_episode: int = 2,
    on_batch: Callable[[int, int, str, int], None] | None = None,
) -> tuple[list[Candidate], list[Rejection], list[str]]:
    """Returns (candidates, schema rejections, tags of batches that never returned valid JSON)."""
    context = series_context(episodes)
    groups = batches(episodes, per_call)
    candidates: list[Candidate] = []
    rejections: list[Rejection] = []
    failed: list[str] = []
    for i, group in enumerate(groups, 1):
        tag = f"find-{i:02d}-E{group[0].number:02d}-E{group[-1].number:02d}"
        user = prompts.finder_user(context, [render_episode(e) for e in group], per_episode * len(group))
        try:
            batch = llm.complete_json(prompts.FINDER_SYSTEM, user, RawBatch, tag=tag)
        except (LLMError, BudgetExceeded) as err:
            log.error("%s skipped: %s", tag, err)
            failed.append(tag)
            continue
        found = 0
        for raw in batch.candidates:
            try:
                candidates.append(Candidate.model_validate(raw))
                found += 1
            except ValidationError as err:
                rejections.append(Rejection(raw=raw, reason=f"schema ({err.error_count()} errors)"))
        log.info("%s: %d candidates", tag, found)
        if on_batch:
            on_batch(i, len(groups), tag, found)
    return candidates, rejections, failed


def uncovered(episodes: list[Episode], promos: list[Promo]) -> list[int]:
    """Episode numbers that no valid promo uses (reported, never silently ignored)."""
    covered = {s.episode for p in promos for s in p.segments}
    return [e.number for e in episodes if e.number not in covered]
