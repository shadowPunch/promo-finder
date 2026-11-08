import json

from helpers import duel_reply, duels_in, fake_llm, fixture_episodes, make_candidate, make_engagement, make_promo
from promo_finder_v2 import prompts
from promo_finder_v2.duels import consistency, duel_winner, judge, round_robin, split_half_agreement, win_shares
from promo_finder_v2.models import Duel, Moment
from promo_finder_v2.validate import validate

EPISODES = fixture_episodes()
# p1 and p2 judged in both orders: viewer A picks p1 both times, viewer B follows the order
DUELS = [Duel("M01", "p1", "p2", pick_a="p1", pick_b="p2", why=""),
         Duel("M01", "p2", "p1", pick_a="p1", pick_b="p1", why="")]


def _cuts():
    original = validate(make_candidate(), EPISODES)
    longer = validate(make_candidate(segments=[{"start": "E01L001", "end": "E01L008"}], cliffhanger_ref="E01L008",
                                     change="sinker"), EPISODES)  # ends on the stepmother's frozen face
    for cut in (original, longer):
        cut.moment_id, cut.engagement = "M01", make_engagement(50)
    return original, longer


def test_win_shares_weight_viewer_a_and_b():
    assert win_shares(DUELS, weight_a=0.65) == {"p1": 0.825, "p2": 0.175}
    assert win_shares([]) == {}


def test_consistency_reports_order_agreement_and_position_bias():
    assert consistency(DUELS) == {"n": 2, "pairs_both_orders": 1, "order_agreement": 0.5, "order_agreement_a": 1.0,
                                  "order_agreement_b": 0.0, "first_shown_win_rate": 0.25}
    assert consistency([])["order_agreement"] is None


def test_duel_winner_uses_win_share_then_absolute_score_then_length():
    p1 = make_promo([(1, 0.0, 30.0)], promo_id="p1")
    p2 = make_promo([(1, 0.0, 25.0)], promo_id="p2")
    p1.engagement, p2.engagement = make_engagement(40), make_engagement(70)
    assert duel_winner([p1, p2], DUELS) is p1                    # wins more duels despite the lower score
    tied = [Duel("M01", "p1", "p2", "p1", "p1", ""), Duel("M01", "p2", "p1", "p2", "p2", "")]
    assert duel_winner([p1, p2], tied) is p2                     # tie: higher absolute score
    p2.engagement = make_engagement(40)
    assert duel_winner([p1, p2], tied) is p2                     # still tied: shorter cut
    assert duel_winner([p1, p2], []) is None


def test_split_half_agreement_compares_winners_picked_from_each_order_alone():
    p1, p2, p3 = (make_promo([(1, 0.0, 30.0)], promo_id=pid) for pid in ("p1", "p2", "p3"))
    for p in (p1, p2, p3):
        p.engagement = make_engagement(50)
    steady = Moment("M01", p1, [p1, p2], duels=[Duel("M01", "p1", "p2", "p2", "p2", ""),
                                               Duel("M01", "p2", "p1", "p2", "p2", "")])
    # p3 is this moment's refined version: its duel against the winner is left out of the split
    flaky = Moment("M02", p1, [p1, p2, p3], refined=p3,
                   duels=[Duel("M02", "p1", "p2", "p1", "p1", ""), Duel("M02", "p2", "p1", "p2", "p2", ""),
                          Duel("M02", "p3", "p2", "p3", "p3", "")])
    assert split_half_agreement([steady, flaky]) == 0.5
    assert split_half_agreement([Moment("M03", p1, [p1])]) is None


def test_round_robin_pairs_only_scored_versions_of_each_moment():
    original, longer = _cuts()
    unscored = validate(make_candidate(segments=[{"start": "E01L002", "end": "E01L007"}], change="hook"), EPISODES)
    pairs = round_robin([Moment("M01", original, [original, longer, unscored])])
    assert pairs == [("M01", original, longer)]


def test_judge_shows_each_pair_in_both_orders_in_separate_calls(tmp_path):
    original, longer = _cuts()
    llm = fake_llm(lambda r: duel_reply(r["messages"][1]["content"]), tmp_path)
    duels, failed = judge([("M01", original, longer)], EPISODES, llm)

    assert failed == [] and len(llm.client.requests) == 2
    assert sorted((d.shown_first, d.shown_second) for d in duels) == sorted(
        [(original.promo_id, longer.promo_id), (longer.promo_id, original.promo_id)])
    assert all(d.pick_a == d.pick_b == longer.promo_id for d in duels)
    for request in llm.client.requests:
        assert request["messages"][0]["content"] == prompts.DUEL_SYSTEM
        assert list(duels_in(request["messages"][1]["content"])) == ["D01"]
    assert consistency(duels)["order_agreement"] == 1.0


def test_judge_retries_a_missing_duel_once_then_leaves_it_out(tmp_path):
    original, longer = _cuts()
    replies = [json.dumps({"duels": []}),                                         # first order: missing
               json.dumps({"duels": [{"duel": "D01", "why": "w", "pick": ["X", "Z"]}]}),  # retry: invalid
               json.dumps({"duels": [{"duel": "D01", "why": "w", "pick": ["Y", "Y"]}]})]  # swapped order
    llm = fake_llm(replies, tmp_path)
    duels, failed = judge([("M01", original, longer)], EPISODES, llm)
    assert failed == [] and len(duels) == 1 and len(llm.client.requests) == 3
    assert "Last time some duels came back missing" in llm.client.requests[1]["messages"][1]["content"]


def test_a_failed_duel_call_is_recorded_not_raised(tmp_path):
    def gateway_down(request):
        raise RuntimeError("gateway down")

    original, longer = _cuts()
    duels, failed = judge([("M01", original, longer)], EPISODES, fake_llm(gateway_down, tmp_path))
    assert duels == [] and failed == ["duel-01", "duel-swap-01"]
