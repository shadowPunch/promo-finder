from helpers import audience_reply, duel_reply, editor_reply, fake_llm, fixture_episodes, make_candidate
from promo_finder import prompts
from promo_finder.tournament import change_win_rates, ranks, refine_uplift, run_tournament, spearman
from promo_finder.validate import validate

EPISODES = fixture_episodes()


def _reply(request):
    system, user = request["messages"][0]["content"], request["messages"][1]["content"]
    if system == prompts.EDITOR_SYSTEM:
        return editor_reply(user)
    if system == prompts.DUEL_SYSTEM:
        return duel_reply(user)  # the cut with the frozen face wins; otherwise the first-shown cut
    # clips that end on episode 1's last block ("frozen face") leave viewers needing more
    return audience_reply(user, need_for=lambda text: (5, 5) if "frozen face" in text else (2, 2))


def test_ranks_and_spearman():
    assert ranks([5, 5, 1]) == [2.5, 2.5, 1.0]
    assert spearman([1, 2, 3], [1, 2, 3]) == 1.0
    assert spearman([1, 2, 3], [3, 2, 1]) == -1.0
    assert spearman([1, 2], [1, 2]) is None
    assert spearman([1, 1, 1], [1, 2, 3]) is None


def _shortlist():
    e1 = validate(make_candidate(), EPISODES)
    e2 = validate(make_candidate(title="The portrait", segments=[{"start": "E02L001", "end": "E02L004"}],
                                 hook_ref="E02L001", cliffhanger_ref="E02L004"), EPISODES)
    return [e1, e2]


def test_tournament_by_score_keeps_the_best_version_refines_and_checks_reliability(tmp_path):
    editor_llm, audience_llm = fake_llm(_reply, tmp_path / "e"), fake_llm(_reply, tmp_path / "a")
    result = run_tournament(_shortlist(), EPISODES, editor_llm, audience_llm, n_versions=3, refine_top=1,
                            use_duels=False)

    m1, m2 = result.moments
    assert [v.candidate.change for v in m1.versions] == ["original", "sinker", "refine"]
    assert m1.winner.candidate.change == "sinker" and m1.refined is not None
    assert m2.refined is None and m2.winner.candidate.change == "original"
    assert [(p.moment_id, p.rank) for p in result.winners] == [("M01", 1), ("M02", 2)]
    assert result.failed == [] and result.rejections == []
    assert result.reliability == {"n": 2, "spearman": None, "mean_abs_change": 0.0}
    assert len(editor_llm.client.requests) == 2 and len(audience_llm.client.requests) == 3
    assert change_win_rates(result.moments) == {"original": 0.5, "refine": 0.0, "sinker": 0.5}
    uplift = refine_uplift(result.moments)
    assert uplift["tried"] == 1 and uplift["won"] == 0 and uplift["mean_gain"] < 0
    assert result.duels == {} and all(v.win_share is None for m in result.moments for v in m.versions)


def test_tournament_by_duels_picks_winners_head_to_head_and_settles_refine_by_duel(tmp_path):
    editor_llm, audience_llm = fake_llm(_reply, tmp_path / "e"), fake_llm(_reply, tmp_path / "a")
    result = run_tournament(_shortlist(), EPISODES, editor_llm, audience_llm, n_versions=3, refine_top=1)

    m1, m2 = result.moments
    assert m1.winner.candidate.change == "sinker" and m1.refined is not None   # won all 4 of its duels
    assert [v.win_share for v in m1.versions] == [0.0, 1.0, 0.0]
    assert len(m1.duels) == 4                                                    # round robin + refine, both orders
    assert m2.winner.candidate.change == "original"     # duels split 1-1 by position: tie, higher absolute score
    assert [v.win_share for v in m2.versions] == [0.5, 0.5]
    # duel calls: round robin + swap, refine + swap; plus audience, refine audience and reliability
    assert len(audience_llm.client.requests) == 7 and result.failed == []
    stats = result.duels
    assert (stats["n"], stats["missing"], stats["pairs_both_orders"]) == (6, 0, 3)
    assert stats["order_agreement"] == 0.667 and stats["first_shown_win_rate"] == 0.667
    assert stats["same_winner_as_score"] == 1.0
    assert stats["split_half_same_winner"] == 0.5    # M01 steady; M02's position-biased picks flip with the order
    assert refine_uplift(result.moments)["won"] == 0


def test_tournament_with_nothing_shortlisted_makes_no_calls(tmp_path):
    llm = fake_llm([], tmp_path)
    result = run_tournament([], EPISODES, llm, llm)
    assert result.winners == [] and result.reliability["n"] == 0 and llm.client.requests == []
