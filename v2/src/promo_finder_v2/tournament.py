"""The version tournament: score every version with the simulated audience, keep each moment's best, give the top few
one improvement round, then re-score some winners in a new order to measure how stable the scores are."""
from __future__ import annotations

import logging
import statistics
from collections import Counter
from dataclasses import dataclass, field

from . import audience, editor, engagement
from .llm import LLM
from .models import Episode, Moment, Promo, Rejection
from .screen import dedupe
from .transcript import clip_lines

log = logging.getLogger(__name__)


@dataclass
class TournamentResult:
    moments: list[Moment]
    winners: list[Promo]          # ranked by engagement, footage duplicates removed
    rejections: list[Rejection]   # rejected editor versions
    failed: list[str]             # tags of model calls that failed
    reliability: dict = field(default_factory=dict)


def engagement_of(p: Promo) -> float:
    return p.engagement.score if p.engagement else -1.0


def best_version(versions: list[Promo]) -> Promo | None:
    """Highest engagement; ties go to the shorter cut. Unscored versions can't win."""
    scored = [v for v in versions if v.engagement]
    return max(scored, key=lambda v: (v.engagement.score, -v.duration)) if scored else None


def ranks(values: list[float]) -> list[float]:
    """1-based ranks; ties share their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            result[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return result


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    try:
        return round(statistics.correlation(ranks(xs), ranks(ys)), 3)
    except statistics.StatisticsError:  # one side is constant
        return None


def run_tournament(shortlisted: list[Promo], episodes: dict[int, Episode], llm_editor: LLM, llm_audience: LLM,
                   n_versions: int = 3, refine_top: int = 5, reliability_n: int = 8, weight_a: float = 0.65,
                   seed: int = 0) -> TournamentResult:
    moments: list[Moment] = []
    for i, p in enumerate(shortlisted, 1):
        p.moment_id = f"M{i:02d}"
        moments.append(Moment(p.moment_id, p, [p]))
    rejections: list[Rejection] = []
    failed: list[str] = []
    if moments and n_versions > 0:
        rejections, failed = editor.make_versions(moments, episodes, llm_editor, n_versions)

    versions = [v for m in moments for v in m.versions]
    scores, missed = audience.score_clips(versions, episodes, llm_audience, weight_a, seed=seed, tag="audience")
    audience.apply(versions, scores)
    failed += missed
    for m in moments:
        m.winner = best_version(m.versions)

    top = sorted((m for m in moments if m.winner), key=lambda m: engagement_of(m.winner), reverse=True)[:refine_top]
    if top:
        notes = {m.moment_id: engagement.diagnose(clip_lines(m.winner, episodes), m.winner.reaction,
                                                  m.winner.engagement) for m in top}
        more_rejections, more_failed = editor.refine(top, episodes, llm_editor, notes)
        rejections += more_rejections
        failed += more_failed
        refined = [m.refined for m in top if m.refined]
        scores, missed = audience.score_clips(refined, episodes, llm_audience, weight_a, seed=seed, tag="refine")
        audience.apply(refined, scores)
        failed += missed
        for m in top:
            if m.refined and engagement_of(m.refined) > engagement_of(m.winner):
                m.winner = m.refined

    winners = dedupe([m.winner for m in moments if m.winner], key=engagement_of)
    for rank, p in enumerate(winners, 1):
        p.rank = rank
    reliability = check_reliability(winners[:reliability_n], episodes, llm_audience, weight_a, seed + 1)
    failed += reliability.pop("failed")
    return TournamentResult(moments, winners, rejections, failed, reliability)


def check_reliability(promos: list[Promo], episodes: dict[int, Episode], llm: LLM, weight_a: float,
                      seed: int) -> dict:
    """Re-score already-scored promos in a different order and compare the two passes."""
    promos = [p for p in promos if p.engagement]
    if not promos:
        return {"n": 0, "spearman": None, "mean_abs_change": None, "failed": []}
    scores, failed = audience.score_clips(promos, episodes, llm, weight_a, seed=seed, tag="reliability")
    pairs = [(p.engagement.score, scores[p.promo_id][1].score) for p in promos if p.promo_id in scores]
    return {
        "n": len(pairs),
        "spearman": spearman([a for a, _ in pairs], [b for _, b in pairs]),
        "mean_abs_change": round(statistics.mean(abs(a - b) for a, b in pairs), 2) if pairs else None,
        "failed": failed,
    }


def change_win_rates(moments: list[Moment]) -> dict[str, float]:
    """For each change type: share of moments it won, among moments where a scored version of that type existed."""
    tried: Counter = Counter()
    won: Counter = Counter()
    for m in moments:
        tried.update({v.candidate.change for v in m.versions if v.engagement})
        if m.winner:
            won[m.winner.candidate.change] += 1
    return {kind: round(won[kind] / tried[kind], 3) for kind in sorted(tried)}


def refine_uplift(moments: list[Moment]) -> dict:
    """How the refine round did: versions tried, how many beat the previous best, and the mean score change."""
    gains = []
    for m in moments:
        if m.refined and m.refined.engagement:
            before = best_version([v for v in m.versions if v is not m.refined])
            if before:
                gains.append(m.refined.engagement.score - before.engagement.score)
    return {"tried": len(gains), "won": sum(g > 0 for g in gains),
            "mean_gain": round(statistics.mean(gains), 2) if gains else None}
