"""Head-to-head duels: the simulated viewers see two cuts of the same moment and each picks the one they would engage
with more. One absolute audience pass proved too noisy to pick between versions; judges are steadier at "X or Y?".

Every pair is judged in both orders, in separate calls, so a bias towards the first- or second-shown cut cancels out.
A version's win share is its weighted share of picks: viewer A counts `weight_a`, viewer B the rest."""
from __future__ import annotations

import logging
import random
from collections import defaultdict
from itertools import combinations

from . import prompts
from .audience import judge_in_batches
from .budget import BudgetExceeded
from .llm import LLM, LLMError
from .models import Duel, DuelVerdict, Episode, Moment, Promo, RawDuels
from .transcript import clip_lines, render_clip

log = logging.getLogger(__name__)
DUELS_PER_CALL = 12

Matchup = tuple[str, Promo, Promo]  # moment id and two cuts of that moment


def round_robin(moments: list[Moment]) -> list[Matchup]:
    """Every pair of each moment's scored versions (unscored versions can't win, so they don't play)."""
    return [(m.moment_id, x, y) for m in moments
            for x, y in combinations([v for v in m.versions if v.engagement], 2)]


def judge(matchups: list[Matchup], episodes: dict[int, Episode], llm: LLM, per_call: int = DUELS_PER_CALL,
          seed: int = 0, tag: str = "duel") -> tuple[list[Duel], list[str]]:
    """Judges every matchup twice, once in each order; the two orders never share a call.
    Returns (duels, tags of calls that failed)."""
    rng = random.Random(seed)
    first = [(mid, y, x) if rng.random() < 0.5 else (mid, x, y) for mid, x, y in matchups]
    swapped = [(mid, y, x) for mid, x, y in first]
    rng.shuffle(first)
    rng.shuffle(swapped)
    duels: list[Duel] = []
    failed: list[str] = []
    for order, name in ((first, tag), (swapped, f"{tag}-swap")):
        judge_in_batches(order, per_call, name, lambda group, call, retry:
                         _judge_group(group, episodes, llm, call, retry, duels, failed))
    return duels, failed


def win_shares(duels: list[Duel], weight_a: float = 0.65) -> dict[str, float]:
    """promo_id -> weighted share of picks won across the duels it played."""
    won: dict[str, float] = defaultdict(float)
    played: dict[str, int] = defaultdict(int)
    for d in duels:
        played[d.shown_first] += 1
        played[d.shown_second] += 1
        won[d.pick_a] += weight_a
        won[d.pick_b] += 1 - weight_a
    return {pid: round(won[pid] / n, 3) for pid, n in played.items()}


def duel_winner(versions: list[Promo], duels: list[Duel], weight_a: float = 0.65) -> Promo | None:
    """Highest win share; ties go to the higher absolute score, then the shorter cut. None if nothing was judged."""
    shares = win_shares(duels, weight_a)
    contenders = [v for v in versions if v.engagement and v.promo_id in shares]
    if not contenders:
        return None
    return max(contenders, key=lambda v: (shares[v.promo_id], v.engagement.score, -v.duration))


def consistency(duels: list[Duel]) -> dict:
    """How steady the judge is. Order agreement: share of pair x viewer judgments that picked the same cut in both
    orders (0.5 = chance). First-shown win rate: share of picks that went to cut X (0.5 = no position bias)."""
    by_pair: dict[tuple, dict[str, Duel]] = defaultdict(dict)
    for d in duels:
        by_pair[(d.moment_id, frozenset((d.shown_first, d.shown_second)))][d.shown_first] = d
    agree_a, agree_b = [], []
    for orders in by_pair.values():
        if len(orders) == 2:
            one, other = orders.values()
            agree_a.append(one.pick_a == other.pick_a)
            agree_b.append(one.pick_b == other.pick_b)
    return {
        "n": len(duels),
        "pairs_both_orders": len(agree_a),
        "order_agreement": share(agree_a + agree_b),
        "order_agreement_a": share(agree_a),
        "order_agreement_b": share(agree_b),
        "first_shown_win_rate": share([pick == d.shown_first for d in duels for pick in (d.pick_a, d.pick_b)]),
    }


def split_half_agreement(moments: list[Moment], weight_a: float = 0.65) -> float | None:
    """Share of moments whose round-robin winner is the same when picked from each half alone (one order of every
    pair per half). The answer to "would a second pass pick the same cut?" with half the evidence each time."""
    same = []
    for m in moments:
        refined = m.refined.promo_id if m.refined else None
        played = [d for d in m.duels if refined not in (d.shown_first, d.shown_second)]
        halves = ([d for d in played if d.shown_first < d.shown_second],
                  [d for d in played if d.shown_first > d.shown_second])
        first, second = (duel_winner(m.versions, half, weight_a) for half in halves)
        if first and second:
            same.append(first is second)
    return share(same)


def share(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 3) if flags else None


def _judge_group(group: list[Matchup], episodes: dict[int, Episode], llm: LLM, tag: str, retry: bool,
                 duels: list[Duel], failed: list[str]) -> list[Matchup]:
    """Judges one call's duels into `duels`; returns the matchups whose verdict was missing or invalid."""
    by_id = {f"D{j:02d}": matchup for j, matchup in enumerate(group, 1)}
    shown = [(duel_id, render_clip(clip_lines(x, episodes)), render_clip(clip_lines(y, episodes)))
             for duel_id, (_, x, y) in by_id.items()]
    try:
        result = llm.complete_json(prompts.DUEL_SYSTEM, prompts.duel_user(shown, retry), RawDuels, tag=tag)
    except (LLMError, BudgetExceeded) as err:
        log.error("%s failed: %s", tag, err)
        failed.append(tag)
        return []
    judged: set[str] = set()
    for raw in result.duels:
        duel_id = raw.get("duel")
        if duel_id not in by_id or duel_id in judged:
            continue
        try:
            verdict = DuelVerdict.model_validate(raw)
        except ValueError as err:  # pydantic's ValidationError is a ValueError
            log.warning("%s %s: %s", tag, duel_id, str(err)[:200])
            continue
        moment_id, x, y = by_id[duel_id]
        cut = {"X": x.promo_id, "Y": y.promo_id}
        duels.append(Duel(moment_id, x.promo_id, y.promo_id, cut[verdict.pick[0]], cut[verdict.pick[1]], verdict.why))
        judged.add(duel_id)
    return [matchup for duel_id, matchup in by_id.items() if duel_id not in judged]
