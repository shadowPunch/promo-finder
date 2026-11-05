import json
import re

import pytest

from helpers import fake_llm, fixture_episodes, make_promo
from promo_finder import rank as ranking


def test_rule_score_weights_penalty_and_early_bonus():
    early = make_promo([(1, 0.0, 26.0)])  # scores 5/4/4, low spoiler risk
    late_spoiler = make_promo([(20, 0.0, 26.0)], spoiler_risk="high")
    assert ranking.rule_score(early) == pytest.approx(4.65)       # 4.4 + 0.25 early bonus
    assert ranking.rule_score(late_spoiler) == pytest.approx(3.65)  # 4.4 - 0.75 spoiler penalty


def test_dedupe_keeps_best_of_overlapping_promos():
    a = make_promo([(1, 0.0, 26.0)], promo_id="a")
    b = make_promo([(1, 2.0, 26.0)], promo_id="b")
    c = make_promo([(2, 0.0, 36.0)], promo_id="c")
    a.rule_score, b.rule_score, c.rule_score = 4.0, 3.0, 2.0
    assert [p.promo_id for p in ranking.dedupe([b, c, a])] == ["a", "c"]


def test_judge_verdicts_drive_the_final_rank(tmp_path):
    slap = make_promo([(1, 0.0, 26.0)], promo_id="slap")
    portrait = make_promo([(2, 0.0, 36.0)], promo_id="portrait")
    unjudged = make_promo([(1, 26.0, 40.0)], promo_id="unjudged")
    slap.rule_score, portrait.rule_score, unjudged.rule_score = 4.65, 4.0, 1.0

    def reply(request):
        user = request["messages"][1]["content"]
        verdicts = []
        for clip_id, body in re.findall(r"### CLIP (C\d+)\n(.*?)(?=\n\n### CLIP|\n\nFor EVERY clip)", user, re.S):
            score = 5 if "That's my face" in body else 1
            verdicts.append({"clip": clip_id, "understood": "x", "stops_scroll": score,
                             "needs_next": score, "overall": score})
        return json.dumps({"verdicts": verdicts})

    ranking.judge([slap, portrait, unjudged], fixture_episodes(), fake_llm(reply, tmp_path), top_k=2)
    ranked = ranking.rank([slap, portrait, unjudged])
    assert [p.promo_id for p in ranked] == ["portrait", "slap", "unjudged"]
    assert [p.rank for p in ranked] == [1, 2, 3]
    assert unjudged.verdict is None
