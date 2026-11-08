import json

from helpers import fake_llm, fixture_episodes, make_candidate, make_promo
from promo_finder_v2 import prompts
from promo_finder_v2.finder import batches, find_candidates, uncovered


def test_batches_split_in_order():
    assert [len(b) for b in batches(list(range(5)), 2)] == [2, 2, 1]


def test_find_candidates_validates_each_candidate_and_skips_broken_batches(tmp_path):
    good = make_candidate().model_dump()

    def reply(request):
        user = request["messages"][1]["content"]
        if "=== EPISODE 1 " in user:
            return json.dumps({"candidates": [good, {"title": "missing fields"}]})
        return "not json"

    llm = fake_llm(reply, tmp_path)
    seen = []
    candidates, rejected, failed = find_candidates(
        list(fixture_episodes().values()), llm, per_call=1, per_episode=2,
        on_batch=lambda i, total, tag, found: seen.append((i, total, found)),
    )
    assert [c.title for c in candidates] == [good["title"]]
    assert [r.reason.split()[0] for r in rejected] == ["schema"]
    assert failed == ["find-02-E02-E02"]
    assert seen == [(1, 2, 1)]

    first_prompt = llm.client.requests[0]["messages"][1]["content"]
    assert "E01L003 [00:02.00-00:05.00]" in first_prompt
    assert "E02: Mara discovers the ring" in first_prompt  # series context covers every episode
    assert "up to 2" in first_prompt
    assert "sinker_question" in first_prompt and "explosive" in llm.client.requests[0]["messages"][0]["content"]
    assert llm.client.requests[0]["messages"][0]["content"] == prompts.FINDER_SYSTEM


def test_uncovered_lists_episodes_without_a_valid_promo():
    episodes = list(fixture_episodes().values())
    assert uncovered(episodes, [make_promo([(1, 0.0, 26.0)])]) == [2]
