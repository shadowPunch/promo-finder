"""Engagement score for one clip, computed in code from the simulated audience's line-by-line reaction.

Per viewer: 25 points each for hook (share still watching at 3 s), completion (share still watching at the end),
punch (the strongest of explosive / funny / puzzling / shocking) and sinker (need to know next x how varied the
imagined next scenes are), minus up to 15 points for confusion. The two viewers are blended 65/35 by default.
The weights are a stated assumption; every component is kept so they can be fitted to real metrics later."""
from __future__ import annotations

import math

from .models import ClipReaction, Engagement, ViewerScore
from .transcript import ClipLine

ENGINE_OF = {"anger": "explosive", "amusement": "funny", "intrigue": "puzzling", "shock": "shocking"}
HOOK_AT_S = 3.0
PART = 25.0          # points per component
MAX_PENALTY = 15.0   # points
BONUS = 0.1          # punch bonus for an early surprise, and for emotions that rise and fall (Teixeira et al. 2012)
STRONG = 2           # strength that counts as a clear emotion


def survival_at(t: float, starts: list[float], leaves: list[int]) -> float:
    """Share still watching at time t: viewers may leave during every line that began before t."""
    share = 1.0
    for start, leave in zip(starts, leaves):
        if start < t:
            share *= 1 - leave / 100
    return share


def curve(starts: list[float], leaves: list[int], duration: float) -> list[float]:
    return [round(survival_at(t, starts, leaves), 4) for t in range(math.ceil(duration) + 1)]


def punch(starts: list[float], beats: list) -> tuple[float, str | None]:
    """Peak strength among the four engine emotions (0-1) plus bonuses, and the engine holding the peak."""
    peak, engine = 0, None
    for _, emotion, strength, _, _ in beats:
        if emotion in ENGINE_OF and strength > peak:
            peak, engine = strength, ENGINE_OF[emotion]
    value = peak / 3
    if any(emotion in ("shock", "intrigue") and strength >= STRONG and start < HOOK_AT_S
           for start, (_, emotion, strength, _, _) in zip(starts, beats)):
        value += BONUS
    strong = [emotion for _, emotion, strength, _, _ in beats if strength >= STRONG and emotion != "none"]
    if sum(a != b for a, b in zip(strong, strong[1:])) >= 2:
        value += BONUS
    return min(value, 1.0), engine


def spread(likelihoods: list[float]) -> float:
    """Normalised entropy of the imagined next scenes: 1 = all equally likely, 0 = one obvious answer."""
    total = sum(likelihoods)
    if len(likelihoods) < 2 or total <= 0:
        return 0.0
    probs = [p / total for p in likelihoods if p > 0]
    return -sum(p * math.log(p) for p in probs) / math.log(len(likelihoods))


def sinker(need_next: int, spread_value: float) -> float:
    return (need_next - 1) / 4 * (0.5 + 0.5 * spread_value)


def confusion_penalty(beats: list) -> float:
    if not beats:
        return 0.0
    return MAX_PENALTY * sum(strength / 3 for _, emotion, strength, _, _ in beats if emotion == "confusion") / len(beats)


def score(lines: list[ClipLine], reaction: ClipReaction, weight_a: float = 0.65) -> Engagement:
    """`reaction.beats` must be in clip-line order (audience.check_reaction guarantees it)."""
    starts = [line.start for line in lines]
    duration = max((line.end for line in lines), default=0.0)
    peak, engine = punch(starts, reaction.beats)
    spread_value = spread([likelihood for _, likelihood in reaction.next])
    penalty = confusion_penalty(reaction.beats)

    def viewer(column: int, need: int) -> ViewerScore:
        leaves = [beat[column] for beat in reaction.beats]
        hook = survival_at(HOOK_AT_S, starts, leaves)
        completion = survival_at(math.inf, starts, leaves)
        sink = sinker(need, spread_value)
        total = PART * (hook + completion + peak + sink) - penalty
        return ViewerScore(round(hook, 4), round(completion, 4), round(sink, 4),
                           round(max(0.0, min(100.0, total)), 2), curve(starts, leaves, duration))

    a, b = viewer(3, reaction.need_next[0]), viewer(4, reaction.need_next[1])
    return Engagement(a, b, round(peak, 4), engine, round(spread_value, 4), round(penalty, 2),
                      round(weight_a * a.score + (1 - weight_a) * b.score, 2))


def diagnose(lines: list[ClipLine], reaction: ClipReaction, eng: Engagement) -> str:
    """Plain-language weak spots, given to the editor in the refine round."""
    line, beat = max(zip(lines, reaction.beats), key=lambda pair: pair[1][3])
    notes = [f"Biggest drop: {line.line} at +{line.start:.1f}s ({beat[1]}, {beat[3]}% of viewer A leave)."]
    likelihoods = [likelihood for _, likelihood in reaction.next]
    top = max(likelihoods) / (sum(likelihoods) or 1.0)
    notes.append(f"Sinker: the most likely imagined next scene has {top:.0%} likelihood (spread {eng.spread:.2f}); "
                 "aim for several believable answers.")
    confusing = [l.line for l, b in zip(lines, reaction.beats) if b[1] == "confusion"]
    if confusing:
        notes.append(f"Confusing lines: {', '.join(confusing)}.")
    notes.append(f"Viewer A: hook {eng.a.hook:.0%}, completion {eng.a.completion:.0%}; punch {eng.punch:.2f}; "
                 f"engagement {eng.score:.1f}.")
    return " ".join(notes)
