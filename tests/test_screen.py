import json

import pytest

from helpers import clip_blocks, fake_llm, fixture_episodes, make_promo
from promo_finder import prompts
from promo_finder.models import Verdict
from promo_finder.screen import dedupe, screen, screen_score, shortlist


def _verdict(overall):
    return Verdict(clip="C01", understood="u", stops_scroll=3, needs_next=3, overall=overall)


def _screened(promo_id, segments, overall):
    promo = make_promo(segments, promo_id=promo_id)
    promo.verdict = _verdict(overall)
    return promo


def test_screen_sets_verdicts_in_batches(tmp_path):
    promos = [make_promo([(1, 0.0, 26.0)], promo_id="a"), make_promo([(2, 0.0, 36.0)], promo_id="b"),
              make_promo([(1, 26.0, 40.0)], promo_id="c")]

    def reply(request):
        user = request["messages"][1]["content"]
        return json.dumps({"verdicts": [{"clip": c, "understood": "x", "stops_scroll": 3, "needs_next": 3,
                                         "overall": 5 if "That's my face" in text else 2}
                                        for c, text in clip_blocks(user).items()]})

    llm = fake_llm(reply, tmp_path)
    assert screen(promos, fixture_episodes(), llm, batch_size=2) == []
    assert len(llm.client.requests) == 2
    assert {p.promo_id: p.verdict.overall for p in promos} == {"a": 2, "b": 5, "c": 2}
    assert llm.client.requests[0]["messages"][0]["content"] == prompts.SCREEN_SYSTEM


def test_screen_records_failed_batches(tmp_path):
    assert screen([make_promo([(1, 0.0, 26.0)])], fixture_episodes(), fake_llm(["bad"] * 3, tmp_path)) == ["screen-01"]


def test_screen_score_adds_the_early_episode_bonus():
    assert screen_score(_screened("e", [(1, 0.0, 26.0)], 4)) == pytest.approx(4.25)
    assert screen_score(_screened("l", [(20, 0.0, 26.0)], 4)) == pytest.approx(4.0)
    assert screen_score(make_promo([(20, 0.0, 26.0)])) == 0.0


def test_shortlist_takes_one_per_episode_and_skips_overlaps():
    a = _screened("a", [(1, 0.0, 26.0)], 5)
    b = _screened("b", [(1, 26.0, 40.0)], 4)  # same episode as a
    c = _screened("c", [(2, 0.0, 36.0)], 3)
    d = _screened("d", [(3, 0.0, 30.0)], 2)
    assert [p.promo_id for p in shortlist([d, c, b, a], k=2)] == ["a", "c"]
    assert [p.promo_id for p in shortlist([d, c, b, a], k=10)] == ["a", "c", "d"]


def test_dedupe_keeps_the_best_of_overlapping_promos():
    a, b, c = (make_promo([(1, 0.0, 26.0)], promo_id="a"), make_promo([(1, 2.0, 26.0)], promo_id="b"),
               make_promo([(2, 0.0, 36.0)], promo_id="c"))
    score = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert [p.promo_id for p in dedupe([b, c, a], key=lambda p: score[p.promo_id])] == ["a", "c"]
