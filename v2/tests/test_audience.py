import json

import pytest

from helpers import audience_reply, clips_in, fake_llm, fixture_episodes, make_promo
from promo_finder_v2 import prompts
from promo_finder_v2.audience import apply, check_reaction, score_clips
from promo_finder_v2.budget import Budget
from promo_finder_v2.transcript import ClipLine

LINES = [ClipLine("L01", 0.0, 2.0, "x", False), ClipLine("L02", 2.0, 5.0, "y", False)]


def _raw(beats):
    return {"clip": "C01", "understood": "u", "question": "q", "next": [["a", 1], ["b", 1]], "need_next": [3, 3],
            "beats": beats}


def test_check_reaction_reorders_beats_and_rejects_bad_coverage():
    reaction = check_reaction(_raw([["L02", "joy", 1, 0, 0], ["L01", "shock", 2, 5, 5]]), LINES)
    assert [beat[0] for beat in reaction.beats] == ["L01", "L02"]
    with pytest.raises(ValueError, match=r"missing \['L02'\]"):
        check_reaction(_raw([["L01", "shock", 2, 5, 5]]), LINES)
    with pytest.raises(ValueError, match=r"duplicate or unknown \['L01'\]"):
        check_reaction(_raw([["L01", "shock", 2, 5, 5], ["L01", "joy", 1, 0, 0]]), LINES)
    with pytest.raises(ValueError):
        check_reaction(_raw([["L01", "angry", 2, 5, 5], ["L02", "joy", 1, 0, 0]]), LINES)


def test_score_clips_retries_incomplete_clips_once(tmp_path):
    a, b = make_promo([(1, 0.0, 26.0)], promo_id="a"), make_promo([(2, 0.0, 36.0)], promo_id="b")
    calls = []

    def reply(request):
        user = request["messages"][1]["content"]
        calls.append(user)
        if len(calls) == 1:
            return audience_reply(user, skip={next(iter(clips_in(user)))})
        return audience_reply(user)

    scores, failed = score_clips([a, b], fixture_episodes(), fake_llm(reply, tmp_path))
    assert set(scores) == {"a", "b"} and failed == []
    assert len(calls) == 2 and "came back incomplete" in calls[1] and len(clips_in(calls[1])) == 1
    reaction, eng = scores["a"]
    assert len(reaction.beats) == 7 and 0 < eng.score <= 100
    apply([a, b], scores)
    assert a.engagement is eng and b.reaction is not None


def test_clips_still_invalid_after_the_retry_stay_unscored(tmp_path):
    a = make_promo([(1, 0.0, 26.0)], promo_id="a")
    scores, failed = score_clips([a], fixture_episodes(), fake_llm(lambda r: json.dumps({"clips": []}), tmp_path))
    assert scores == {} and failed == []


def test_prompt_is_blind_and_numbered(tmp_path):
    llm = fake_llm(lambda r: audience_reply(r["messages"][1]["content"]), tmp_path)
    score_clips([make_promo([(1, 0.0, 26.0)], promo_id="a")], fixture_episodes(), llm)
    system, user = (m["content"] for m in llm.client.requests[0]["messages"])
    assert system == prompts.AUDIENCE_SYSTEM and "Viewer A" in system and "Viewer B" in system
    assert "L01 [+00.0-02.0] CAMERA: Wide shot of a crowded ballroom." in user
    assert "Slapped at the party" not in user and "E01L001" not in user


def test_failed_and_budget_stopped_calls_are_recorded(tmp_path):
    a = make_promo([(1, 0.0, 26.0)], promo_id="a")
    scores, failed = score_clips([a], fixture_episodes(), fake_llm(["bad"] * 3, tmp_path / "x"))
    assert scores == {} and failed == ["audience-01"]
    llm = fake_llm([], tmp_path / "y")
    llm.budget = Budget(cap_usd=0.0)
    assert score_clips([a], fixture_episodes(), llm) == ({}, ["audience-01"])
