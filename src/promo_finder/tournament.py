"""The version tournament: score every version with the simulated audience, pick each moment's best in one-on-one
comparisons (or by absolute score with comparisons off), give the top few one improvement round, then re-score some winners in a
new order to measure how stable the absolute scores are."""
from __future__ import annotations

import logging
import statistics
from collections import Counter
from dataclasses import dataclass, field

from . import audience, duels, editor, engagement
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
    duels: dict = field(default_factory=dict)  # duel consistency stats; empty when duels are off


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
                   seed: int = 0, use_duels: bool = True, duel_batch: int = duels.DUELS_PER_CALL) -> TournamentResult:
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
    expected_duels, same_as_score = 0, None
    if use_duels:
        expected_duels, same_as_score, missed = _pick_by_duels(moments, episodes, llm_audience, weight_a,
                                                               duel_batch, seed)
        failed += missed

    top = sorted((m for m in moments if m.winner), key=lambda m: engagement_of(m.winner), reverse=True)[:refine_top]
    if top:
        more_rejections, missed, expected = _refine(top, episodes, llm_editor, llm_audience, weight_a, seed,
                                                    use_duels, duel_batch)
        rejections += more_rejections
        failed += missed
        expected_duels += expected
    duel_stats = _duel_summary(moments, weight_a, expected_duels, same_as_score) if use_duels else {}

    winners = dedupe([m.winner for m in moments if m.winner], key=engagement_of)
    for rank, p in enumerate(winners, 1):
        p.rank = rank
    reliability = check_reliability(winners[:reliability_n], episodes, llm_audience, weight_a, seed + 1)
    failed += reliability.pop("failed")
    return TournamentResult(moments, winners, rejections, failed, reliability, duel_stats)


def _pick_by_duels(moments: list[Moment], episodes: dict[int, Episode], llm: LLM, weight_a: float, per_call: int,
                   seed: int) -> tuple[int, float | None, list[str]]:
    """Round-robin duels in each moment; the duel winner replaces the top absolute score (kept if nothing was judged).
    Returns (duels expected, share of moments where both methods agree, failed call tags)."""
    matchups = duels.round_robin(moments)
    found, failed = duels.judge(matchups, episodes, llm, per_call, seed, tag="duel")
    same = []
    for m in moments:
        m.duels = [d for d in found if d.moment_id == m.moment_id]
        by_duel = duels.duel_winner(m.versions, m.duels, weight_a)
        if by_duel:
            same.append(by_duel is m.winner)
            m.winner = by_duel
    return 2 * len(matchups), duels.share(same), failed


def _refine(top: list[Moment], episodes: dict[int, Episode], llm_editor: LLM, llm_audience: LLM, weight_a: float,
            seed: int, use_duels: bool, per_call: int) -> tuple[list[Rejection], list[str], int]:
    """One improvement round for the top moments. An improved version replaces the winner only if it wins head to
    head (or, without duels, scores higher). Returns (rejected versions, failed call tags, duels expected)."""
    notes = {m.moment_id: engagement.diagnose(clip_lines(m.winner, episodes), m.winner.reaction, m.winner.engagement)
             for m in top}
    rejections, failed = editor.refine(top, episodes, llm_editor, notes)
    refined = [m.refined for m in top if m.refined]
    scores, missed = audience.score_clips(refined, episodes, llm_audience, weight_a, seed=seed, tag="refine")
    audience.apply(refined, scores)
    failed += missed
    contenders = [m for m in top if m.refined and m.refined.engagement]
    if not use_duels:
        for m in contenders:
            if engagement_of(m.refined) > engagement_of(m.winner):
                m.winner = m.refined
        return rejections, failed, 0
    matchups = [(m.moment_id, m.refined, m.winner) for m in contenders]
    found, missed = duels.judge(matchups, episodes, llm_audience, per_call, seed, tag="refine-duel")
    failed += missed
    for m in contenders:
        head_to_head = [d for d in found if d.moment_id == m.moment_id]
        m.duels += head_to_head
        if duels.win_shares(head_to_head, weight_a).get(m.refined.promo_id, 0.0) > 0.5:
            m.winner = m.refined
    return rejections, failed, 2 * len(matchups)


def _duel_summary(moments: list[Moment], weight_a: float, expected: int, same_as_score: float | None) -> dict:
    """Stores each version's win share and returns the run's duel stats."""
    all_duels = [d for m in moments for d in m.duels]
    for m in moments:
        shares = duels.win_shares(m.duels, weight_a)
        for v in m.versions:
            v.win_share = shares.get(v.promo_id)
    return {**duels.consistency(all_duels), "missing": expected - len(all_duels),
            "split_half_same_winner": duels.split_half_agreement(moments, weight_a),
            "same_winner_as_score": same_as_score}


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
    """How the refine round did: versions tried, how many replaced the winner, and the mean absolute score change."""
    gains = []
    for m in moments:
        if m.refined and m.refined.engagement:
            before = best_version([v for v in m.versions if v is not m.refined])
            if before:
                gains.append(m.refined.engagement.score - before.engagement.score)
    won = sum(m.refined is not None and m.winner is m.refined for m in moments)
    return {"tried": len(gains), "won": won,
            "mean_gain": round(statistics.mean(gains), 2) if gains else None}
