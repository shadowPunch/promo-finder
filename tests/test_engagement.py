import pytest

from promo_finder import engagement
from promo_finder.models import ClipReaction
from promo_finder.transcript import ClipLine

LINES = [ClipLine("L01", 0.0, 2.0, "ACTION: a", False), ClipLine("L02", 2.0, 5.0, "A: b", False),
         ClipLine("L03", 5.0, 10.0, "B: c", False), ClipLine("L04", 10.0, 20.0, "CAMERA: d", False)]
REACTION = ClipReaction(
    clip="C01", understood="u", question="q", next=[("x", 50), ("y", 50)], need_next=(5, 3),
    beats=[("L01", "shock", 3, 10, 20), ("L02", "anger", 2, 0, 10), ("L03", "tension", 1, 10, 10),
           ("L04", "intrigue", 2, 0, 0)],
)


def test_survival_counts_every_line_that_has_started():
    starts, leaves = [0.0, 2.0, 5.0, 10.0], [10, 0, 10, 0]
    assert engagement.survival_at(3.0, starts, leaves) == pytest.approx(0.9)
    curve = engagement.curve(starts, leaves, 20.0)
    assert len(curve) == 21
    assert (curve[0], curve[1], curve[2], curve[6], curve[-1]) == (1.0, 0.9, 0.9, 0.81, 0.81)


def test_punch_takes_the_strongest_engine_and_adds_bonuses():
    assert engagement.punch([0.0, 2.0, 5.0, 10.0], REACTION.beats) == (1.0, "shocking")  # 3/3 + bonuses, capped
    late_laugh = [("L01", "tension", 1, 0, 0), ("L02", "amusement", 2, 0, 0), ("L03", "amusement", 2, 0, 0)]
    value, engine = engagement.punch([0.0, 5.0, 10.0], late_laugh)
    assert value == pytest.approx(2 / 3) and engine == "funny"
    assert engagement.punch([0.0], [("L01", "tension", 3, 0, 0)]) == (0.0, None)


def test_spread_is_normalised_entropy():
    assert engagement.spread([50, 50]) == pytest.approx(1.0)
    assert engagement.spread([80, 20]) == pytest.approx(0.7219, abs=1e-3)
    assert engagement.spread([100, 0]) == 0.0


def test_confusion_penalty_is_at_most_fifteen_points():
    beats = [("L01", "confusion", 3, 0, 0), ("L02", "none", 0, 0, 0)]
    assert engagement.confusion_penalty(beats) == pytest.approx(7.5)


def test_score_matches_the_hand_worked_example():
    eng = engagement.score(LINES, REACTION, weight_a=0.65)
    assert (eng.a.hook, eng.a.completion, eng.a.sinker) == (0.9, 0.81, 1.0)
    assert (eng.b.hook, eng.b.completion, eng.b.sinker) == (0.72, 0.648, 0.5)
    assert eng.a.score == pytest.approx(92.75) and eng.b.score == pytest.approx(71.7)
    assert eng.score == pytest.approx(85.38)
    assert (eng.punch, eng.engine, eng.spread, eng.penalty) == (1.0, "shocking", 1.0, 0.0)
    assert len(eng.a.curve) == 21


def test_diagnose_names_the_biggest_drop_and_the_sinker_spread():
    text = engagement.diagnose(LINES, REACTION, engagement.score(LINES, REACTION))
    assert "Biggest drop: L01 at +0.0s (shock, 10% of viewer A leave)" in text
    assert "50% likelihood" in text and "Confusing" not in text
